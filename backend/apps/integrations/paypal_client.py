"""HTTP client for the verified PayPal REST endpoints used by PayPilot.

Only these operations are implemented (see docs/paypal-integration.md):

* POST /v1/oauth2/token — application client-credentials
* GET  /v1/reporting/transactions — Transaction Search
* GET  /v2/invoicing/invoices — list invoices
* GET  /v2/invoicing/invoices/{id} — invoice detail
* POST /v2/invoicing/invoices/{id}/remind — official invoice reminder (write; not retried)

No other endpoints are called. Tokens never leave this module.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache

from apps.integrations.exceptions import (
    PayPalError,
    PayPalInvalidCredentials,
    PayPalNotConfigured,
    PayPalPermissionDenied,
    PayPalRateLimited,
    PayPalTimeout,
    PayPalUnavailable,
)

logger = logging.getLogger("paypilot.paypal")

SANDBOX_HOST = "https://api-m.sandbox.paypal.com"
LIVE_HOST = "https://api-m.paypal.com"
TOKEN_CACHE_PREFIX = "paypal-token:"  # noqa: S105 — cache key, not a credential


def api_host(environment: str | None = None) -> str:
    env = (environment or settings.PAYPAL_ENVIRONMENT or "sandbox").lower()
    if env == "live":
        return LIVE_HOST
    return SANDBOX_HOST


def credentials_configured() -> bool:
    return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)


def _raise_for_status(response: requests.Response, *, action: str) -> None:
    status = response.status_code
    if status in (200, 201, 204):
        return
    if status in (401, 400) and action == "token":
        raise PayPalInvalidCredentials()
    if status == 401:
        raise PayPalInvalidCredentials()
    if status == 403:
        raise PayPalPermissionDenied(details={"action": action})
    if status == 429:
        retry_after = response.headers.get("Retry-After")
        raise PayPalRateLimited(details={"retry_after": retry_after})
    if status >= 500:
        raise PayPalUnavailable(details={"action": action, "http_status": status})
    logger.warning("paypal_unexpected_status", extra={"action": action, "http_status": status})
    raise PayPalError(details={"action": action, "http_status": status})


def _request(method: str, url: str, *, action: str, retry_safe: bool, **kwargs) -> requests.Response:
    timeout = settings.PAYPAL_HTTP_TIMEOUT_SECONDS
    attempts = 1 + (settings.PAYPAL_MAX_RETRIES if retry_safe else 0)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.Timeout as exc:
            last_error = PayPalTimeout()
            logger.warning("paypal_timeout", extra={"action": action, "attempt": attempt + 1})
            if not retry_safe or attempt == attempts - 1:
                raise last_error from exc
            time.sleep(0.4 * (attempt + 1))
            continue
        except requests.RequestException as exc:
            last_error = PayPalUnavailable()
            logger.warning("paypal_transport_error", extra={"action": action, "attempt": attempt + 1})
            if not retry_safe or attempt == attempts - 1:
                raise last_error from exc
            time.sleep(0.4 * (attempt + 1))
            continue
        if response.status_code >= 500 or response.status_code == 429:
            last_error = PayPalUnavailable() if response.status_code >= 500 else PayPalRateLimited()
            if retry_safe and attempt < attempts - 1:
                time.sleep(0.4 * (attempt + 1))
                continue
        _raise_for_status(response, action=action)
        return response
    raise last_error or PayPalUnavailable()


def fetch_access_token() -> str:
    """Client-credentials token for the application's own sandbox (or live) REST app."""
    if not credentials_configured():
        raise PayPalNotConfigured()
    cache_key = TOKEN_CACHE_PREFIX + settings.PAYPAL_ENVIRONMENT
    cached = cache.get(cache_key)
    if cached:
        return cached
    response = _request(
        "POST",
        f"{api_host()}/v1/oauth2/token",
        action="token",
        retry_safe=True,
        data={"grant_type": "client_credentials"},
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json"},
    )
    payload = response.json()
    token = payload.get("access_token")
    expires = int(payload.get("expires_in") or 300)
    if not token:
        raise PayPalInvalidCredentials()
    cache.set(cache_key, token, timeout=max(30, expires - 60))
    return token


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {fetch_access_token()}", "Accept": "application/json"}


def list_transactions(*, start_date: str, end_date: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    query = urlencode(
        {
            "start_date": start_date,
            "end_date": end_date,
            "fields": "all",
            "page": page,
            "page_size": min(page_size, 500),
        }
    )
    response = _request(
        "GET",
        f"{api_host()}/v1/reporting/transactions?{query}",
        action="list_transactions",
        retry_safe=True,
        headers=_auth_headers(),
    )
    return response.json()


def list_invoices(*, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    query = urlencode({"page": page, "page_size": min(page_size, 100), "total_required": "true"})
    response = _request(
        "GET",
        f"{api_host()}/v2/invoicing/invoices?{query}",
        action="list_invoices",
        retry_safe=True,
        headers=_auth_headers(),
    )
    return response.json()


def get_invoice(invoice_id: str) -> dict[str, Any]:
    response = _request(
        "GET",
        f"{api_host()}/v2/invoicing/invoices/{invoice_id}",
        action="get_invoice",
        retry_safe=True,
        headers=_auth_headers(),
    )
    return response.json()


def remind_invoice(invoice_id: str) -> int:
    """POST /v2/invoicing/invoices/{id}/remind.

    Official Invoicing v2 reminder. Success is HTTP 204. Not retried: the call is not
    idempotent and PayPal ignores custom subject/note.
    Documented at https://developer.paypal.com/api/invoicing/v2/invoices-remind
    """
    invoice_id = (invoice_id or "").strip()
    if not invoice_id:
        raise PayPalError(details={"action": "remind_invoice"})
    response = _request(
        "POST",
        f"{api_host()}/v2/invoicing/invoices/{invoice_id}/remind",
        action="remind_invoice",
        retry_safe=False,
        headers={**_auth_headers(), "Content-Type": "application/json"},
        json={"send_to_recipient": True, "send_to_invoicer": True},
    )
    return response.status_code
