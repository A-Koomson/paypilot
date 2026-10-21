"""Consistent API error envelope.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.context import request_id_var

logger = logging.getLogger("paypilot.api")


class ApiError(exceptions.APIException):
    """Domain error with a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None, details: Any = None):
        super().__init__(detail=message, code=code or self.default_code)
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code or self.default_code
        self.details = details


def error_response(
    code: str, message: str, http_status: int, details: Any = None, headers: dict | None = None
) -> Response:
    body = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    if details:
        body["error"]["details"] = details
    return Response(body, status=http_status, headers=headers)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("unhandled_exception", extra={"view": context["view"].__class__.__name__})
        return error_response("server_error", "An unexpected error occurred.", status.HTTP_500_INTERNAL_SERVER_ERROR)

    headers = {k: v for k, v in response.items() if k in ("Retry-After", "WWW-Authenticate")}

    if isinstance(exc, ApiError):
        return error_response(exc.error_code, str(exc.detail), response.status_code, exc.details, headers)
    if isinstance(exc, exceptions.ValidationError):
        return error_response(
            "validation_error", "The submitted data is invalid.", response.status_code, response.data, headers
        )
    if isinstance(exc, exceptions.Throttled):
        return error_response(
            "rate_limited", "Too many requests. Please try again later.", response.status_code, None, headers
        )
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return error_response(
            "not_authenticated", "Authentication is required.", status.HTTP_401_UNAUTHORIZED, None, headers
        )
    if isinstance(exc, exceptions.PermissionDenied):
        code = getattr(exc, "get_codes", lambda: "permission_denied")()
        code = code if isinstance(code, str) and code != "permission_denied" else "permission_denied"
        return error_response(code, str(exc.detail), response.status_code, None, headers)
    if isinstance(exc, exceptions.NotFound):
        return error_response("not_found", "Not found.", response.status_code, None, headers)
    if isinstance(exc, exceptions.MethodNotAllowed):
        return error_response("method_not_allowed", "Method not allowed.", response.status_code, None, headers)
    if isinstance(exc, exceptions.ParseError):
        return error_response("parse_error", "Malformed request body.", response.status_code, None, headers)
    return error_response("error", str(getattr(exc, "detail", "Request failed.")), response.status_code, None, headers)
