"""Read-only tool registry. The model may request a tool; this module validates and executes it."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.utils.dateparse import parse_datetime
from pydantic import BaseModel, Field, ValidationError, field_validator

from apps.core.exceptions import ApiError
from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.merchants.models import Merchant
from apps.recovery.models import RecoveryCase
from apps.recovery.services import list_queue, prepare_draft, refresh_cases, serialize_action

MAX_ROWS = 25

# PayPal Transaction Search status codes we surface. Unknown codes are returned as-is, never remapped to completed.
COMPLETED = {"S"}
PENDING = {"P"}
DENIED = {"D"}
REVERSED = {"V"}
PAID_INVOICE = {"PAID", "MARKED_AS_PAID"}
UNPAID_INVOICE = {"SENT", "UNPAID", "PARTIALLY_PAID", "PAYMENT_PENDING", "SCHEDULED"}


class DateRange(BaseModel):
    start: datetime
    end: datetime

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse(cls, value):
        if isinstance(value, datetime):
            return value
        parsed = parse_datetime(str(value).replace("Z", "+00:00"))
        if parsed is None:
            raise ValueError("Use an ISO-8601 datetime.")
        return parsed

    @field_validator("end")
    @classmethod
    def ordered(cls, end, info):
        start = info.data.get("start")
        if start and end < start:
            raise ValueError("end must be after start.")
        return end


class TransactionQuery(DateRange):
    status: str | None = Field(default=None, max_length=8)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    limit: int = Field(default=20, ge=1, le=MAX_ROWS)


class SummaryQuery(DateRange):
    pass


class DetailQuery(BaseModel):
    record_id: UUID


class InvoiceQuery(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=20, ge=1, le=MAX_ROWS)


class RecoveryQueueQuery(BaseModel):
    limit: int = Field(default=10, ge=1, le=MAX_ROWS)


class DraftReminderQuery(BaseModel):
    invoice_id: UUID


def _money(amount: Decimal, currency: str) -> dict:
    return {"amount": f"{amount:.2f}", "currency": currency}


def _txn_payload(row: PayPalTransaction) -> dict:
    return {
        "id": str(row.id),
        "source_id": row.source_id,
        "status": row.status,
        "status_meaning": (
            "completed"
            if row.status in COMPLETED
            else "pending"
            if row.status in PENDING
            else "denied"
            if row.status in DENIED
            else "reversed"
            if row.status in REVERSED
            else "other"
        ),
        "amount": f"{row.amount:.2f}",
        "currency": row.currency,
        "initiated_at": row.initiated_at.isoformat() if row.initiated_at else None,
        "note": row.note,
    }


def _inv_payload(row: PayPalInvoice) -> dict:
    return {
        "id": str(row.id),
        "source_id": row.source_id,
        "invoice_number": row.invoice_number,
        "status": row.status,
        "amount": f"{row.amount:.2f}",
        "due_amount": f"{row.due_amount:.2f}",
        "currency": row.currency,
        "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
        "counts_as_received": row.status in PAID_INVOICE,
    }


def get_transactions(merchant: Merchant, args: TransactionQuery) -> dict:
    qs = PayPalTransaction.objects.filter(merchant=merchant, initiated_at__gte=args.start, initiated_at__lte=args.end)
    if args.status:
        qs = qs.filter(status=args.status)
    if args.currency:
        qs = qs.filter(currency=args.currency.upper())
    rows = list(qs[: args.limit])
    return {
        "count": len(rows),
        "truncated": qs.count() > args.limit,
        "records": [_txn_payload(r) for r in rows],
        "note": "Statuses are PayPal Transaction Search codes. Pending is not completed.",
    }


def get_payment_summary(merchant: Merchant, args: SummaryQuery) -> dict:
    rows = PayPalTransaction.objects.filter(merchant=merchant, initiated_at__gte=args.start, initiated_at__lte=args.end)
    by_currency: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_currency.setdefault(
            row.currency,
            {
                "currency": row.currency,
                "completed": Decimal("0"),
                "pending": Decimal("0"),
                "other": Decimal("0"),
                "completed_count": 0,
                "pending_count": 0,
                "total_count": 0,
            },
        )
        bucket["total_count"] += 1
        if row.status in COMPLETED:
            bucket["completed"] += row.amount
            bucket["completed_count"] += 1
        elif row.status in PENDING:
            bucket["pending"] += row.amount
            bucket["pending_count"] += 1
        else:
            bucket["other"] += row.amount
    invoices = PayPalInvoice.objects.filter(merchant=merchant)
    invoice_open: dict[str, Decimal] = {}
    for inv in invoices:
        if inv.status in UNPAID_INVOICE:
            invoice_open[inv.currency] = invoice_open.get(inv.currency, Decimal("0")) + inv.due_amount
    return {
        "range": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "by_currency": [
            {
                "currency": c,
                "completed": _money(v["completed"], c),
                "pending": _money(v["pending"], c),
                "other": _money(v["other"], c),
                "completed_count": v["completed_count"],
                "pending_count": v["pending_count"],
                "total_count": v["total_count"],
            }
            for c, v in sorted(by_currency.items())
        ],
        "unpaid_invoices_by_currency": [
            _money(amt, cur) | {"currency": cur} for cur, amt in sorted(invoice_open.items())
        ],
        "notes": [
            "Totals are computed in backend decimal arithmetic, separately per currency.",
            "Pending transactions and unpaid invoices are not money received.",
            "Fees, profit and account balance are not available from the imported fields.",
        ],
    }


def get_payment_details(merchant: Merchant, args: DetailQuery) -> dict:
    row = PayPalTransaction.objects.filter(merchant=merchant, pk=args.record_id).first()
    if row:
        return {"type": "transaction", "record": _txn_payload(row)}
    inv = PayPalInvoice.objects.filter(merchant=merchant, pk=args.record_id).first()
    if inv:
        return {"type": "invoice", "record": _inv_payload(inv)}
    raise ApiError("Record not found.", code="not_found", status_code=404)


def list_recovery_queue(merchant: Merchant, args: RecoveryQueueQuery) -> dict:
    items = list_queue(merchant)[: args.limit]
    return {
        "count": len(items),
        "records": items,
        "note": "Ranking is deterministic from overdue days, amount, status and follow-up history. This tool does not send reminders.",
    }


def draft_payment_reminder(merchant: Merchant, args: DraftReminderQuery) -> dict:
    refresh_cases(merchant)
    invoice = PayPalInvoice.objects.filter(merchant=merchant, pk=args.invoice_id).first()
    if invoice is None:
        raise ApiError("Record not found.", code="not_found", status_code=404)
    case = RecoveryCase.objects.filter(merchant=merchant, invoice=invoice).first()
    if case is None:
        raise ApiError("That invoice is not on the recovery queue.", code="invalid_state", status_code=409)
    action = prepare_draft(merchant, case.id, actor=merchant.user)
    return {
        "draft": serialize_action(action),
        "case_id": str(case.id),
        "sent": False,
        "note": "Draft only. The merchant must review and approve a delivery method before anything is sent.",
    }


def get_invoices(merchant: Merchant, args: InvoiceQuery) -> dict:
    qs = PayPalInvoice.objects.filter(merchant=merchant)
    if args.status:
        qs = qs.filter(status=args.status)
    rows = list(qs[: args.limit])
    return {
        "count": len(rows),
        "truncated": qs.count() > args.limit,
        "records": [_inv_payload(r) for r in rows],
        "note": "Unpaid and sent invoices are not treated as money received.",
    }


class ToolSpec:
    def __init__(self, name: str, description: str, schema: type[BaseModel], handler: Callable):
        self.name = name
        self.description = description
        self.schema = schema
        self.handler = handler

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema.model_json_schema(),
            },
        }


REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "get_transactions",
            "Retrieve the merchant’s imported PayPal transactions for a date range. Status P is pending, S is completed.",
            TransactionQuery,
            get_transactions,
        ),
        ToolSpec(
            "get_payment_summary",
            "Deterministic totals per currency over a date range. Never mixes currencies. Pending is not completed.",
            SummaryQuery,
            get_payment_summary,
        ),
        ToolSpec(
            "get_payment_details",
            "Retrieve one imported transaction or invoice by PayPilot record id. Other merchants’ ids return not found.",
            DetailQuery,
            get_payment_details,
        ),
        ToolSpec(
            "get_invoices",
            "Retrieve imported PayPal invoices. Does not send, create or remind.",
            InvoiceQuery,
            get_invoices,
        ),
        ToolSpec(
            "list_recovery_queue",
            "List outstanding imported invoices on the revenue recovery queue, with explainable priority. Does not send anything.",
            RecoveryQueueQuery,
            list_recovery_queue,
        ),
        ToolSpec(
            "draft_payment_reminder",
            "Prepare a payment reminder draft from a verified invoice. Does not send, email, or call PayPal.",
            DraftReminderQuery,
            draft_payment_reminder,
        ),
    )
}

# Explicitly not registered: anything that writes to PayPal or the merchant account.
FORBIDDEN_TOOL_NAMES = {
    "send_invoice",
    "send_invoice_reminder",
    "create_invoice",
    "refund",
    "pay_order",
    "create_order",
    "change_settings",
}


def execute_tool(merchant: Merchant, name: str, raw_arguments: str) -> dict:
    if name in FORBIDDEN_TOOL_NAMES or name not in REGISTRY:
        return {
            "error": "tool_not_allowed",
            "message": "That tool is not available. Sending, refunds and other writes require a separate merchant approval.",
        }
    spec = REGISTRY[name]
    try:
        args = spec.schema.model_validate(json.loads(raw_arguments or "{}"))
    except (ValidationError, json.JSONDecodeError) as exc:
        return {"error": "invalid_arguments", "message": "The tool arguments were invalid.", "details": str(exc)[:400]}
    try:
        return spec.handler(merchant, args)
    except ApiError as exc:
        return {"error": exc.error_code, "message": str(exc.detail)}


def openai_tools() -> list[dict]:
    return [spec.openai_schema() for spec in REGISTRY.values()]
