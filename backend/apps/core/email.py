"""Email helpers that never claim delivery when none happened."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("paypilot.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"


class DisabledEmailBackend(BaseEmailBackend):
    """Used when no email provider is configured. Sends nothing and says so."""

    def send_messages(self, email_messages):
        logger.warning("email_not_delivered_no_provider_configured", extra={"count": len(email_messages)})
        return 0


@dataclass(frozen=True)
class EmailResult:
    delivered: bool
    mode: str  # "smtp" | "console" | "disabled"


def _resend_api_key() -> str:
    return (getattr(settings, "RESEND_API_KEY", "") or "").strip()


def _deliver_resend(*, to: str, subject: str, body: str, key: str) -> EmailResult:
    """Resend HTTPS. Used on Render because outbound SMTP ports are often blocked."""
    try:
        response = requests.post(
            RESEND_ENDPOINT,
            json={
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "PayPilot/1.0",
            },
            timeout=settings.EMAIL_TIMEOUT,
        )
    except requests.RequestException:
        logger.exception("email_send_failed", extra={"mode": "smtp", "transport": "resend"})
        return EmailResult(delivered=False, mode="smtp")
    if response.status_code >= 400:
        logger.warning("email_send_failed", extra={"mode": "smtp", "transport": "resend", "http_status": response.status_code})
        return EmailResult(delivered=False, mode="smtp")
    return EmailResult(delivered=True, mode="smtp")


def send_email(*, to: str, subject: str, body: str) -> EmailResult:
    """Send a plain-text email. `delivered` is True only when a real provider accepted it."""
    mode = getattr(settings, "EMAIL_DELIVERY_MODE", "disabled")
    key = _resend_api_key()
    if key:
        return _deliver_resend(to=to, subject=subject, body=body, key=key)
    try:
        sent = EmailMessage(subject=subject, body=body, to=[to]).send(fail_silently=False)
    except Exception:  # noqa: BLE001 - provider failures must not crash the request
        logger.exception("email_send_failed", extra={"mode": mode})
        return EmailResult(delivered=False, mode=mode)
    return EmailResult(delivered=bool(sent) and mode == "smtp", mode=mode)
