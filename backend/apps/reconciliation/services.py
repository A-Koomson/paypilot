"""Create orders, run matching, resolve exceptions without rewriting PayPal records."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.exceptions import ApiError
from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.merchants.models import Merchant
from apps.policy.authorization import authorize
from apps.reconciliation.matching import classify_pair, identifier_hits
from apps.reconciliation.models import (
    ExceptionKind,
    ExceptionStatus,
    FulfillmentStatus,
    InternalOrder,
    MatchOutcome,
    ReconciliationException,
    ResolutionEvent,
)

RESOLUTION_CODES = frozenset(
    {
        "matched_manually",
        "not_applicable",
        "duplicate_ignored",
        "awaiting_fulfillment",
        "awaiting_payment",
        "data_accepted",
    }
)


def serialize_order(order: InternalOrder) -> dict:
    return {
        "id": str(order.id),
        "internal_reference": order.internal_reference,
        "external_reference": order.external_reference or None,
        "amount": f"{order.amount:.2f}",
        "currency": order.currency,
        "status": order.status,
        "fulfillment_status": order.fulfillment_status,
        "customer_reference": order.customer_reference or None,
        "created_at": order.created_at,
    }


def serialize_exception(exc: ReconciliationException) -> dict:
    return {
        "id": str(exc.id),
        "kind": exc.kind,
        "outcome": exc.outcome,
        "status": exc.status,
        "severity": exc.severity,
        "explanation": exc.explanation,
        "transaction_id": str(exc.transaction_id) if exc.transaction_id else None,
        "invoice_id": str(exc.invoice_id) if exc.invoice_id else None,
        "order_id": str(exc.order_id) if exc.order_id else None,
        "transaction_source_id": exc.transaction.source_id if exc.transaction else None,
        "invoice_source_id": exc.invoice.source_id if exc.invoice else None,
        "order_reference": exc.order.internal_reference if exc.order else None,
        "resolution_code": exc.resolution_code or None,
        "resolution_note": exc.resolution_note or None,
        "resolved_at": exc.resolved_at,
        "created_at": exc.created_at,
        "history": [
            {
                "id": str(event.id),
                "action": event.action,
                "note": event.note or None,
                "resolution_code": event.resolution_code or None,
                "created_at": event.created_at,
            }
            for event in exc.history.all()
        ],
    }


def create_order(merchant: Merchant, *, actor, data: dict) -> InternalOrder:
    authorize(user=actor, merchant=merchant, action="reconciliation.create_order")
    ref = str(data.get("internal_reference") or "").strip()
    currency = str(data.get("currency") or "").strip().upper()
    try:
        amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, TypeError):
        raise ApiError("Enter a valid order amount.", code="validation_error", status_code=400)
    if not ref or len(ref) > 64:
        raise ApiError("Enter an internal order reference.", code="validation_error", status_code=400)
    if len(currency) != 3:
        raise ApiError("Use a three-letter ISO currency code.", code="validation_error", status_code=400)
    if amount <= 0:
        raise ApiError("Order amount must be greater than zero.", code="invalid_amount", status_code=400)
    if InternalOrder.objects.filter(merchant=merchant, internal_reference=ref).exists():
        raise ApiError("That internal order reference already exists.", code="duplicate_action", status_code=409)
    order = InternalOrder.objects.create(
        merchant=merchant,
        internal_reference=ref,
        external_reference=str(data.get("external_reference") or "")[:64],
        amount=amount,
        currency=currency,
        customer_reference=str(data.get("customer_reference") or "")[:128],
        fulfillment_status=str(data.get("fulfillment_status") or FulfillmentStatus.UNFULFILLED),
    )
    audit.record(
        "reconciliation.order_created",
        actor=actor,
        merchant=merchant,
        target_type="internal_order",
        target_id=order.id,
        metadata={"reference": ref, "currency": currency},
    )
    return order


def _open_exception(merchant: Merchant, **kwargs) -> ReconciliationException:
    existing = ReconciliationException.objects.filter(
        merchant=merchant,
        kind=kwargs["kind"],
        status__in={ExceptionStatus.OPEN, ExceptionStatus.REOPENED},
        transaction=kwargs.get("transaction"),
        invoice=kwargs.get("invoice"),
        order=kwargs.get("order"),
    ).first()
    if existing:
        return existing
    return ReconciliationException.objects.create(merchant=merchant, **kwargs)


def run_matching(merchant: Merchant, *, actor) -> dict:
    authorize(user=actor, merchant=merchant, action="reconciliation.run")
    orders = list(InternalOrder.objects.filter(merchant=merchant).exclude(status="cancelled"))
    invoices = list(PayPalInvoice.objects.filter(merchant=merchant))
    txns = list(PayPalTransaction.objects.filter(merchant=merchant, status="S"))
    created = 0

    # Reset open auto-detected exceptions so a re-run reflects current records.
    ReconciliationException.objects.filter(
        merchant=merchant, status=ExceptionStatus.OPEN, resolution_code=""
    ).delete()

    matched_orders: set = set()
    matched_invoices: set = set()
    matched_txns: set = set()

    for order in orders:
        invoice_hits = [(inv, identifier_hits(order, invoice=inv)) for inv in invoices]
        invoice_hits = [(inv, hits) for inv, hits in invoice_hits if hits]
        txn_hits = [(txn, identifier_hits(order, txn=txn)) for txn in txns]
        txn_hits = [(txn, hits) for txn, hits in txn_hits if hits]

        if len(invoice_hits) + len(txn_hits) > 1:
            _open_exception(
                merchant,
                kind=ExceptionKind.AMBIGUOUS,
                outcome=MatchOutcome.AMBIGUOUS,
                severity="attention",
                explanation="More than one PayPal record shares an identifier with this order. No automatic match was made.",
                order=order,
                invoice=invoice_hits[0][0] if invoice_hits else None,
                transaction=txn_hits[0][0] if txn_hits else None,
            )
            created += 1
            continue

        if invoice_hits:
            invoice, _ = invoice_hits[0]
            outcome = classify_pair(order, invoice=invoice)
            if outcome == MatchOutcome.MATCHED:
                matched_orders.add(order.id)
                matched_invoices.add(invoice.id)
                if invoice.status in {"PAID", "MARKED_AS_PAID"} and order.fulfillment_status == FulfillmentStatus.UNFULFILLED:
                    _open_exception(
                        merchant,
                        kind=ExceptionKind.PAYMENT_UNFULFILLED,
                        outcome=MatchOutcome.MATCHED,
                        severity="warning",
                        explanation="A matching invoice is paid, but the internal order is still unfulfilled.",
                        order=order,
                        invoice=invoice,
                    )
                    created += 1
                continue
            kind = ExceptionKind.CURRENCY_MISMATCH if order.currency != invoice.currency else ExceptionKind.AMOUNT_MISMATCH
            _open_exception(
                merchant,
                kind=kind,
                outcome=MatchOutcome.DATA_INCONSISTENCY,
                severity="attention",
                explanation="A reliable identifier matched, but amount or currency differs. PayPal records were not changed.",
                order=order,
                invoice=invoice,
            )
            created += 1
            continue

        if txn_hits:
            txn, _ = txn_hits[0]
            outcome = classify_pair(order, txn=txn)
            if outcome == MatchOutcome.MATCHED:
                matched_orders.add(order.id)
                matched_txns.add(txn.id)
                if order.fulfillment_status == FulfillmentStatus.UNFULFILLED:
                    _open_exception(
                        merchant,
                        kind=ExceptionKind.PAYMENT_UNFULFILLED,
                        outcome=MatchOutcome.MATCHED,
                        severity="warning",
                        explanation="A matching completed payment exists, but the internal order is still unfulfilled.",
                        order=order,
                        transaction=txn,
                    )
                    created += 1
                continue
            kind = ExceptionKind.CURRENCY_MISMATCH if order.currency != txn.currency else ExceptionKind.AMOUNT_MISMATCH
            _open_exception(
                merchant,
                kind=kind,
                outcome=MatchOutcome.DATA_INCONSISTENCY,
                severity="attention",
                explanation="A reliable identifier matched, but amount or currency differs. PayPal records were not changed.",
                order=order,
                transaction=txn,
            )
            created += 1
            continue

        # Amount/currency/date similarity is only a hint, never a match.
        amount_peers = [
            inv
            for inv in invoices
            if inv.amount == order.amount and inv.currency == order.currency and not order.external_reference
        ]
        if amount_peers:
            _open_exception(
                merchant,
                kind=ExceptionKind.MISSING_SOURCE,
                outcome=MatchOutcome.REQUIRES_MANUAL_REVIEW,
                severity="info",
                explanation="Amount and currency match an invoice, but no reliable identifier was present, so this was not auto-matched.",
                order=order,
                invoice=amount_peers[0],
            )
            created += 1
        else:
            _open_exception(
                merchant,
                kind=ExceptionKind.ORDER_UNPAID,
                outcome=MatchOutcome.UNMATCHED,
                severity="warning",
                explanation="This internal order has no PayPal payment or invoice with a matching identifier.",
                order=order,
            )
            created += 1

    for invoice in invoices:
        if invoice.id in matched_invoices:
            continue
        if invoice.status not in {"PAID", "MARKED_AS_PAID"}:
            continue
        _open_exception(
            merchant,
            kind=ExceptionKind.PAYMENT_UNMATCHED,
            outcome=MatchOutcome.UNMATCHED,
            severity="info",
            explanation="This paid invoice has no internal order with a matching identifier.",
            invoice=invoice,
        )
        created += 1

    for txn in txns:
        if txn.id in matched_txns:
            continue
        _open_exception(
            merchant,
            kind=ExceptionKind.PAYMENT_UNMATCHED,
            outcome=MatchOutcome.UNMATCHED,
            severity="info",
            explanation="This completed PayPal transaction has no internal order with a matching identifier.",
            transaction=txn,
        )
        created += 1

    refs: dict[str, list] = {}
    for txn in txns:
        refs.setdefault(txn.source_id, []).append(txn)
    for _source_id, group in refs.items():
        if len(group) > 1:
            _open_exception(
                merchant,
                kind=ExceptionKind.DUPLICATE,
                outcome=MatchOutcome.POTENTIAL_DUPLICATE,
                severity="attention",
                explanation="Multiple stored transactions share the same PayPal source id for this merchant.",
                transaction=group[0],
            )
            created += 1

    audit.record(
        "reconciliation.ran",
        actor=actor,
        merchant=merchant,
        target_type="merchant",
        target_id=merchant.id,
        metadata={"exceptions_open": ReconciliationException.objects.filter(merchant=merchant, status=ExceptionStatus.OPEN).count()},
    )
    return {
        "orders": len(orders),
        "exceptions_open": ReconciliationException.objects.filter(
            merchant=merchant, status__in={ExceptionStatus.OPEN, ExceptionStatus.REOPENED}
        ).count(),
    }


def list_exceptions(merchant: Merchant, *, status: str = "", kind: str = "") -> list[dict]:
    qs = ReconciliationException.objects.filter(merchant=merchant).select_related("transaction", "invoice", "order")
    if status:
        qs = qs.filter(status=status)
    if kind:
        qs = qs.filter(kind=kind)
    return [serialize_exception(row) for row in qs]


def resolve_exception(merchant: Merchant, exception_id, *, actor, code: str, note: str) -> ReconciliationException:
    authorize(user=actor, merchant=merchant, action="reconciliation.resolve")
    if code not in RESOLUTION_CODES:
        raise ApiError("Choose a supported resolution code.", code="validation_error", status_code=400)
    with transaction.atomic():
        exc = (
            ReconciliationException.objects.select_for_update()
            .filter(merchant=merchant, pk=exception_id)
            .first()
        )
        if exc is None:
            raise ApiError("Exception not found.", code="not_found", status_code=404)
        if exc.status == ExceptionStatus.RESOLVED:
            raise ApiError("This exception is already resolved.", code="already_executed", status_code=409)
        exc.status = ExceptionStatus.RESOLVED
        exc.resolution_code = code
        exc.resolution_note = note[:400]
        exc.resolved_at = timezone.now()
        exc.resolved_by = actor
        exc.save()
        ResolutionEvent.objects.create(exception=exc, actor=actor, action="resolve", note=note[:400], resolution_code=code)
    audit.record(
        "reconciliation.resolved",
        actor=actor,
        merchant=merchant,
        target_type="recon_exception",
        target_id=exc.id,
        metadata={"code": code, "kind": exc.kind},
    )
    return exc


def reopen_exception(merchant: Merchant, exception_id, *, actor, note: str) -> ReconciliationException:
    authorize(user=actor, merchant=merchant, action="reconciliation.reopen")
    with transaction.atomic():
        exc = (
            ReconciliationException.objects.select_for_update()
            .filter(merchant=merchant, pk=exception_id)
            .first()
        )
        if exc is None:
            raise ApiError("Exception not found.", code="not_found", status_code=404)
        if exc.status != ExceptionStatus.RESOLVED:
            raise ApiError("Only a resolved exception can be reopened.", code="invalid_state", status_code=409)
        exc.status = ExceptionStatus.REOPENED
        exc.resolved_at = None
        exc.save(update_fields=["status", "resolved_at", "updated_at"])
        ResolutionEvent.objects.create(exception=exc, actor=actor, action="reopen", note=note[:400])
    audit.record(
        "reconciliation.reopened",
        actor=actor,
        merchant=merchant,
        target_type="recon_exception",
        target_id=exc.id,
    )
    return exc
