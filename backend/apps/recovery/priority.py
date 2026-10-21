"""Deterministic, explainable ranking. No payment-likelihood claims."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.recovery.models import RecoveryCase


def days_overdue(due: date | None, today: date) -> int | None:
    if due is None:
        return None
    return (today - due).days


def score(case: RecoveryCase, *, today: date) -> int:
    invoice = case.invoice
    overdue = days_overdue(invoice.due_date, today)
    overdue_days = max(overdue or 0, 0)
    cents = int((invoice.due_amount or Decimal("0")) * 100)
    follow_up_penalty = 0
    if case.last_follow_up_at:
        # A recent follow-up lowers rank so newer items can surface.
        follow_up_penalty = 400
    status_boost = 50 if invoice.status in {"SENT", "UNPAID", "PARTIALLY_PAID"} else 0
    # Days overdue is the primary rank; amount differentiates same-age items without drowning them.
    return overdue_days * 1500 + min(cents, 50_000) + case.merchant_priority * 2000 + status_boost - follow_up_penalty


def explanation(case: RecoveryCase, *, today: date) -> str:
    invoice = case.invoice
    parts: list[str] = []
    overdue = days_overdue(invoice.due_date, today)
    if overdue is None:
        parts.append("no due date is available from PayPal")
    elif overdue > 0:
        parts.append(f"it is {overdue} days overdue")
    elif overdue == 0:
        parts.append("it is due today")
    else:
        parts.append(f"it is due in {abs(overdue)} days")
    parts.append(f"the outstanding amount is {invoice.due_amount:.2f} {invoice.currency}")
    parts.append(f"PayPal status is {invoice.status or 'unavailable'}")
    if case.merchant_priority:
        parts.append(f"the merchant set priority {case.merchant_priority}")
    if case.last_follow_up_at:
        parts.append("a follow-up has already been recorded")
    else:
        parts.append("no follow-up has been recorded")
    return "This payment request is prioritised because " + ", and ".join(parts) + "."
