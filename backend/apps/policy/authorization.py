"""Central authorisation for sensitive business actions. Frontend checks are not sufficient."""

from __future__ import annotations

from typing import Any

from apps.accounts.models import Role
from apps.core.exceptions import ApiError

SUPPORTED_ACTIONS = frozenset(
    {
        "recovery.draft",
        "recovery.submit",
        "recovery.approve",
        "recovery.reject",
        "recovery.execute",
        "reconciliation.create_order",
        "reconciliation.run",
        "reconciliation.resolve",
        "reconciliation.reopen",
    }
)

REQUIRES_EXPLICIT_APPROVAL = frozenset(
    {
        "recovery.execute",
    }
)


def authorize(
    *,
    user,
    merchant,
    action: str,
    record: Any = None,
    approved: bool = False,
    already_executed: bool = False,
    eligible: bool = True,
    amount_valid: bool = True,
) -> None:
    if user is None or not getattr(user, "is_authenticated", False):
        raise ApiError("Authentication is required.", code="not_authenticated", status_code=401)
    if getattr(user, "role", None) != Role.MERCHANT:
        raise ApiError("This action is limited to merchant accounts.", code="permission_denied", status_code=403)
    linked = getattr(user, "merchant", None)
    if linked is None or linked.pk != merchant.pk:
        raise ApiError("Not found.", code="not_found", status_code=404)
    if action not in SUPPORTED_ACTIONS:
        raise ApiError("That action is not supported.", code="unsupported_action", status_code=400)
    if record is not None and getattr(record, "merchant_id", None) != merchant.pk:
        raise ApiError("Not found.", code="not_found", status_code=404)
    if not eligible:
        raise ApiError("This record is not eligible for that action.", code="invalid_state", status_code=409)
    if not amount_valid:
        raise ApiError("The amount or currency is not valid for this action.", code="invalid_amount", status_code=400)
    if already_executed:
        raise ApiError("This action has already been executed.", code="already_executed", status_code=409)
    if action in REQUIRES_EXPLICIT_APPROVAL and not approved:
        raise ApiError(
            "Explicit approval is required before this action can run.",
            code="approval_required",
            status_code=403,
        )
