"""Authorisation policies. Roles and the second-factor policy are enforced here, server-side."""

from __future__ import annotations

from rest_framework import exceptions, permissions

from apps.accounts.models import Role, SecurityPolicy

SESSION_SECOND_FACTOR_KEY = "second_factor_at"


class SecondFactorRequired(exceptions.PermissionDenied):
    default_code = "second_factor_required"
    default_detail = "Complete the emailed verification code to continue."


def second_factor_satisfied(request) -> bool:
    """True when this session either does not need, or has completed, the second factor."""
    user = request.user
    if not user.is_authenticated or user.role != Role.MERCHANT:
        return True
    if not SecurityPolicy.load().require_second_factor:
        return True
    return bool(request.session.get(SESSION_SECOND_FACTOR_KEY))


class IsMerchant(permissions.BasePermission):
    """Authenticated merchant whose session satisfies the current second-factor policy."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role != Role.MERCHANT:
            raise exceptions.PermissionDenied("This area is for merchant accounts.")
        if not second_factor_satisfied(request):
            raise SecondFactorRequired()
        return True


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.SUPER_ADMIN)


def get_merchant(request):
    """The merchant that owns the current session. Never derived from client-supplied ids."""
    merchant = getattr(request.user, "merchant", None)
    if merchant is None:
        raise exceptions.PermissionDenied("No merchant profile is linked to this account.")
    return merchant
