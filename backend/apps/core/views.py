"""Project-level error handlers returning the standard JSON envelope."""

from __future__ import annotations

from django.http import JsonResponse

from apps.core.context import request_id_var


def _envelope(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}, status=status
    )


def not_found(request, exception=None):
    return _envelope("not_found", "Not found.", 404)


def server_error(request):
    return _envelope("server_error", "An unexpected error occurred.", 500)
