"""Request-scoped middleware."""

from __future__ import annotations

import logging
import re
import time
import uuid

from django.conf import settings
from django.contrib.auth import logout

from apps.core.context import request_id_var

logger = logging.getLogger("paypilot.request")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


class RequestIDMiddleware:
    """Attaches a request id (accepting a well-formed upstream id) and logs each request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.request_id = request_id
        started = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        if not request.path.startswith("/api/health/"):
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 1),
                    "request_id": request_id,
                },
            )
        return response


class SessionLifetimeMiddleware:
    """Enforces an absolute session lifetime on top of Django's sliding idle timeout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            started = request.session.get("auth_at")
            if started is None:
                request.session["auth_at"] = int(time.time())
            elif time.time() - started > settings.SESSION_ABSOLUTE_SECONDS:
                logout(request)
        return self.get_response(request)
