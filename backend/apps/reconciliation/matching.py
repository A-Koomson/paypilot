"""Deterministic payment-to-order matching. Amount/currency alone never auto-match."""

from __future__ import annotations

from decimal import Decimal

from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.reconciliation.models import InternalOrder, MatchOutcome


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def identifier_hits(order: InternalOrder, *, invoice: PayPalInvoice | None = None, txn: PayPalTransaction | None = None) -> list[str]:
    hits: list[str] = []
    ref = _norm(order.external_reference)
    if not ref:
        return hits
    if invoice:
        if ref == _norm(invoice.source_id):
            hits.append("invoice_source_id")
        if invoice.invoice_number and ref == _norm(invoice.invoice_number):
            hits.append("invoice_number")
    if txn:
        if ref == _norm(txn.source_id):
            hits.append("transaction_source_id")
    internal = _norm(order.internal_reference)
    if invoice and invoice.invoice_number and internal == _norm(invoice.invoice_number):
        hits.append("internal_equals_invoice_number")
    if txn and internal == _norm(txn.source_id):
        hits.append("internal_equals_transaction_id")
    return hits


def money_equal(left_amount: Decimal, left_currency: str, right_amount: Decimal, right_currency: str) -> tuple[bool, str | None]:
    if left_currency != right_currency:
        return False, "currency"
    if left_amount != right_amount:
        return False, "amount"
    return True, None


def classify_pair(order: InternalOrder, *, invoice: PayPalInvoice | None = None, txn: PayPalTransaction | None = None) -> str:
    hits = identifier_hits(order, invoice=invoice, txn=txn)
    if not hits:
        return MatchOutcome.UNMATCHED
    record_amount = invoice.amount if invoice is not None else txn.amount  # type: ignore[union-attr]
    record_currency = invoice.currency if invoice is not None else txn.currency  # type: ignore[union-attr]
    equal, mismatch = money_equal(order.amount, order.currency, record_amount, record_currency)
    if not equal:
        return MatchOutcome.DATA_INCONSISTENCY if mismatch else MatchOutcome.REQUIRES_MANUAL_REVIEW
    return MatchOutcome.MATCHED
