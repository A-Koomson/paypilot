"""Mapped PayPal integration errors. Views convert these to API error codes."""

from __future__ import annotations


class PayPalError(Exception):
    code = "paypal_error"
    status_code = 502
    public_message = "PayPal could not complete that request."

    def __init__(self, message: str | None = None, *, details: dict | None = None):
        super().__init__(message or self.public_message)
        self.details = details or {}


class PayPalNotConfigured(PayPalError):
    code = "not_configured"
    status_code = 503
    public_message = "PayPal credentials are not configured on the server."


class PayPalInvalidCredentials(PayPalError):
    code = "invalid_credentials"
    status_code = 502
    public_message = "PayPal rejected the stored credentials."


class PayPalPermissionDenied(PayPalError):
    code = "paypal_permission_denied"
    status_code = 502
    public_message = "The PayPal app is missing a required permission for this operation."


class PayPalRateLimited(PayPalError):
    code = "paypal_rate_limited"
    status_code = 503
    public_message = "PayPal rate-limited the request. Try again shortly."


class PayPalTimeout(PayPalError):
    code = "paypal_timeout"
    status_code = 504
    public_message = "PayPal did not respond in time."


class PayPalUnavailable(PayPalError):
    code = "paypal_unavailable"
    status_code = 503
    public_message = "PayPal is temporarily unavailable."
