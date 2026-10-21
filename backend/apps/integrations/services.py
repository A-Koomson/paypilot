"""PayPal verification and synchronisation. Views never call PayPal directly."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.audit import services as audit
from apps.integrations import paypal_client
from apps.integrations.exceptions import PayPalError, PayPalNotConfigured
from apps.integrations.models import PayPalConnection, PayPalInvoice, PayPalTransaction
from apps.merchants.models import Merchant, OnboardingStatus

logger = logging.getLogger("paypilot.paypal")

# Transaction Search accepts at most 31 days per request (PayPal documented limit).
WINDOW_DAYS = 31


def connection_for(merchant: Merchant) -> PayPalConnection:
    conn, _ = PayPalConnection.objects.get_or_create(
        merchant=merchant, defaults={"environment": settings.PAYPAL_ENVIRONMENT}
    )
    return conn


def connection_summary(merchant: Merchant) -> dict:
    configured = paypal_client.credentials_configured()
    conn = PayPalConnection.objects.filter(merchant=merchant).first()
    if conn is None:
        return {
            "state": "not_connected" if configured else "not_configured",
            "environment": settings.PAYPAL_ENVIRONMENT,
            "last_synced_at": None,
        }
    return {
        "state": conn.state(configured=configured),
        "environment": conn.environment or settings.PAYPAL_ENVIRONMENT,
        "last_synced_at": conn.last_synced_at,
        "last_verified_at": conn.last_verified_at,
        "last_error_code": conn.last_error_code or None,
        "last_error_message": conn.last_error_message or None,
        "transactions_imported": conn.transactions_imported,
        "invoices_imported": conn.invoices_imported,
        "capabilities": conn.capabilities,
    }


def _record_error(conn: PayPalConnection, exc: PayPalError) -> None:
    conn.last_error_code = exc.code
    conn.last_error_message = exc.public_message
    conn.save(update_fields=["last_error_code", "last_error_message", "updated_at"])


def verify_credentials(merchant: Merchant) -> PayPalConnection:
    conn = connection_for(merchant)
    conn.environment = settings.PAYPAL_ENVIRONMENT
    try:
        paypal_client.fetch_access_token()
    except PayPalError as exc:
        _record_error(conn, exc)
        raise
    conn.last_verified_at = timezone.now()
    conn.last_error_code = ""
    conn.last_error_message = ""
    conn.save(update_fields=["environment", "last_verified_at", "last_error_code", "last_error_message", "updated_at"])
    merchant.advance_onboarding(OnboardingStatus.PAYPAL_CONNECTED)
    audit.record("paypal.verified", actor=merchant.user, target_type="merchant", target_id=merchant.id)
    return conn


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _as_datetime(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(str(value).replace("+0000", "+00:00"))
    return parsed


def _as_date(value: Any):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = parse_date(str(value)[:10])
    return parsed


def _date_windows(lookback_days: int) -> list[tuple[str, str]]:
    end = timezone.now()
    start = end - timedelta(days=lookback_days)
    windows: list[tuple[str, str]] = []
    cursor = start
    while cursor < end:
        nxt = min(cursor + timedelta(days=WINDOW_DAYS), end)
        windows.append((cursor.isoformat(timespec="seconds"), nxt.isoformat(timespec="seconds")))
        cursor = nxt
    return windows


def _upsert_transaction(merchant: Merchant, detail: dict) -> bool:
    info = detail.get("transaction_info") or {}
    source_id = str(info.get("transaction_id") or "").strip()
    if not source_id:
        return False
    amount_info = info.get("transaction_amount") or {}
    currency = str(amount_info.get("currency_code") or "").upper()
    if len(currency) != 3:
        return False
    payer = detail.get("payer_info") or {}
    name = payer.get("payer_name") or {}
    note = str(info.get("transaction_note") or name.get("alternate_full_name") or "")[:240]
    _, created = PayPalTransaction.objects.update_or_create(
        merchant=merchant,
        source_id=source_id,
        defaults={
            "status": str(info.get("transaction_status") or "")[:8],
            "event_code": str(info.get("transaction_event_code") or "")[:16],
            "amount": _as_decimal(amount_info.get("value")),
            "currency": currency,
            "initiated_at": _as_datetime(info.get("transaction_initiation_date")),
            "updated_at_source": _as_datetime(info.get("transaction_updated_date")),
            "payer_email": str(payer.get("email_address") or "")[:254],
            "note": note,
        },
    )
    return created


def _upsert_invoice(merchant: Merchant, item: dict) -> bool:
    source_id = str(item.get("id") or "").strip()
    if not source_id:
        return False
    detail = item.get("detail") or {}
    amount = item.get("amount") or {}
    due = item.get("due_amount") or {}
    currency = str(amount.get("currency_code") or detail.get("currency_code") or "").upper()
    if len(currency) != 3:
        return False
    primary = (item.get("primary_recipients") or [{}])[0]
    billing = (primary.get("billing_info") or {}) if isinstance(primary, dict) else {}
    _, created = PayPalInvoice.objects.update_or_create(
        merchant=merchant,
        source_id=source_id,
        defaults={
            "invoice_number": str(detail.get("invoice_number") or "")[:64],
            "status": str(item.get("status") or "")[:32],
            "amount": _as_decimal(amount.get("value")),
            "due_amount": _as_decimal(due.get("value") if due else amount.get("value")),
            "currency": currency,
            "invoice_date": _as_date(detail.get("invoice_date")),
            "due_date": _as_date(
                detail.get("payment_term", {}).get("due_date") if isinstance(detail.get("payment_term"), dict) else None
            ),
            "recipient_email": str(billing.get("email_address") or "")[:254],
        },
    )
    return created


def _sync_transactions(merchant: Merchant) -> tuple[int, int]:
    created = scanned = 0
    for start, end in _date_windows(settings.PAYPAL_SYNC_LOOKBACK_DAYS):
        page = 1
        total_pages = 1
        while page <= total_pages:
            payload = paypal_client.list_transactions(start_date=start, end_date=end, page=page)
            details = payload.get("transaction_details") or []
            total_pages = int(payload.get("total_pages") or 1)
            for detail in details:
                scanned += 1
                if _upsert_transaction(merchant, detail):
                    created += 1
            page += 1
    return created, scanned


def _sync_invoices(merchant: Merchant) -> tuple[int, int]:
    created = scanned = 0
    page = 1
    total_pages = 1
    while page <= total_pages:
        payload = paypal_client.list_invoices(page=page)
        items = payload.get("items") or []
        total_pages = int(payload.get("total_pages") or 1)
        for item in items:
            scanned += 1
            if _upsert_invoice(merchant, item):
                created += 1
        page += 1
    return created, scanned


def synchronise(merchant: Merchant) -> dict:
    if not paypal_client.credentials_configured():
        raise PayPalNotConfigured()
    conn = verify_credentials(merchant)
    capabilities = {"transactions": False, "invoices": False}
    errors: dict[str, str] = {}
    txn_created = txn_scanned = inv_created = inv_scanned = 0
    try:
        txn_created, txn_scanned = _sync_transactions(merchant)
        capabilities["transactions"] = True
    except PayPalError as exc:
        errors["transactions"] = exc.code
        logger.warning("paypal_sync_transactions_failed", extra={"code": exc.code})
    try:
        inv_created, inv_scanned = _sync_invoices(merchant)
        capabilities["invoices"] = True
    except PayPalError as exc:
        errors["invoices"] = exc.code
        logger.warning("paypal_sync_invoices_failed", extra={"code": exc.code})

    conn.capabilities = capabilities
    conn.transactions_imported = PayPalTransaction.objects.filter(merchant=merchant).count()
    conn.invoices_imported = PayPalInvoice.objects.filter(merchant=merchant).count()
    conn.last_synced_at = timezone.now()
    if errors and not any(capabilities.values()):
        conn.last_error_code = next(iter(errors.values()))
        conn.last_error_message = "PayPal did not return any supported record type."
    elif errors:
        conn.last_error_code = "partial"
        conn.last_error_message = "Some PayPal endpoints could not be read. See capabilities."
    else:
        conn.last_error_code = ""
        conn.last_error_message = ""
    conn.save()
    if conn.transactions_imported or conn.invoices_imported:
        merchant.advance_onboarding(OnboardingStatus.SYNCED)
    audit.record(
        "paypal.synced",
        actor=merchant.user,
        target_type="merchant",
        target_id=merchant.id,
        metadata={
            "capabilities": capabilities,
            "errors": errors,
            "txn_created": txn_created,
            "inv_created": inv_created,
        },
    )
    return {
        "capabilities": capabilities,
        "errors": errors,
        "transactions": {"created": txn_created, "scanned": txn_scanned, "stored": conn.transactions_imported},
        "invoices": {"created": inv_created, "scanned": inv_scanned, "stored": conn.invoices_imported},
        "connection": connection_summary(merchant),
    }
