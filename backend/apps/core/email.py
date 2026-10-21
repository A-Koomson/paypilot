"""Email helpers that never claim delivery when none happened."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("paypilot.email")


class DisabledEmailBackend(BaseEmailBackend):
    """Used when no email provider is configured. Sends nothing and says so."""

    def send_messages(self, email_messages):
        logger.warning("email_not_delivered_no_provider_configured", extra={"count": len(email_messages)})
        return 0


@dataclass(frozen=True)
class EmailResult:
    delivered: bool
    mode: str  # "smtp" | "console" | "disabled"


def send_email(*, to: str, subject: str, body: str) -> EmailResult:
    """Send a plain-text email. `delivered` is True only when a real provider accepted it."""
    mode = getattr(settings, "EMAIL_DELIVERY_MODE", "disabled")
    try:
        sent = EmailMessage(subject=subject, body=body, to=[to]).send(fail_silently=False)
    except Exception:  # noqa: BLE001 - provider failures must not crash the request
        logger.exception("email_send_failed", extra={"mode": mode})
        return EmailResult(delivered=False, mode=mode)
    return EmailResult(delivered=bool(sent) and mode == "smtp", mode=mode)
