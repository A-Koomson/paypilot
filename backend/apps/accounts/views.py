"""Authentication, account and administrator endpoints.

Browser sessions are HTTP-only cookies with CSRF protection. No token is ever returned to the
client. One-time codes and reset tokens are only ever delivered by email.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import serializers as s
from apps.accounts import services
from apps.accounts.models import OneTimeCodePurpose, Role, SecurityPolicy, User
from apps.audit import services as audit
from apps.audit.models import AuditEvent
from apps.core.exceptions import ApiError
from apps.core.pagination import StandardPagination
from apps.core.permissions import SESSION_SECOND_FACTOR_KEY, IsSuperAdmin, second_factor_satisfied
from apps.merchants.serializers import MerchantSerializer

PENDING_2FA_KEY = "pending_second_factor_user"
OAUTH_STATE_KEY = "google_oauth_state"
OAUTH_VERIFIER_KEY = "google_oauth_verifier"


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")) or "unknown"


def _email_payload(result) -> dict:
    return {"delivered": result.delivered, "delivery_mode": result.mode}


def _me_payload(request) -> dict:
    user: User = request.user
    merchant = getattr(user, "merchant", None)
    return {
        "user": s.UserSerializer(user).data,
        "merchant": MerchantSerializer(merchant).data if merchant else None,
        "second_factor_required": not second_factor_satisfied(request),
        "paypal": _paypal_summary(merchant),
    }


def _paypal_summary(merchant) -> dict | None:
    if merchant is None:
        return None
    from apps.integrations.services import connection_summary

    return connection_summary(merchant)


def _complete_login(request, user: User, *, second_factor_done: bool) -> None:
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.cycle_key()
    request.session["auth_at"] = int(time.time())
    request.session.pop(PENDING_2FA_KEY, None)
    if second_factor_done:
        request.session[SESSION_SECOND_FACTOR_KEY] = int(time.time())
    services.ensure_merchant(user)
    audit.record("auth.login", actor=user, target_type="user", target_id=user.id)


# --- Public configuration ----------------------------------------------------------------------------
@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: dict}, tags=["auth"], auth=[])
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class AuthConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: dict}, tags=["auth"], auth=[])
    def get(self, request):
        return Response(
            {
                "google_enabled": services.google_enabled(),
                "email_delivery_mode": getattr(settings, "EMAIL_DELIVERY_MODE", "disabled"),
                "second_factor_required": SecurityPolicy.load().require_second_factor,
                "password_min_length": 10,
                "otp_ttl_seconds": settings.OTP_TTL_SECONDS,
            }
        )


# --- Registration & password sign-in ---------------------------------------------------------------------
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.RegisterSerializer, responses={201: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.register_merchant(**ser.validated_data)
        verification = services.send_email_verification(user)
        _complete_login(request, user, second_factor_done=False)
        if SecurityPolicy.load().require_second_factor:
            # New accounts must also satisfy the policy before protected endpoints respond.
            services.issue_code(user, OneTimeCodePurpose.SECOND_FACTOR)
        return Response(
            {"status": "authenticated", **_me_payload(request), "verification_email": _email_payload(verification)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.LoginSerializer, responses={200: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        user = services.authenticate_password(
            request=request, email=email, password=ser.validated_data["password"], ip=_client_ip(request)
        )
        if user.role == Role.MERCHANT and SecurityPolicy.load().require_second_factor:
            # Do not establish the session yet; park the user id until the emailed code is verified.
            request.session.flush()
            request.session[PENDING_2FA_KEY] = str(user.id)
            issued = services.issue_code(user, OneTimeCodePurpose.SECOND_FACTOR)
            return Response(
                {
                    "status": "second_factor_required",
                    "email": _email_payload(issued.email),
                    "expires_at": issued.expires_at,
                }
            )
        _complete_login(request, user, second_factor_done=False)
        return Response({"status": "authenticated", **_me_payload(request)})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request):
        if request.user.is_authenticated:
            audit.record("auth.logout", actor=request.user, target_type="user", target_id=request.user.id)
        django_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: dict}, tags=["auth"])
    def get(self, request):
        return Response(_me_payload(request))

    @extend_schema(request=s.UserSerializer, responses={200: dict}, tags=["auth"])
    def patch(self, request):
        ser = s.UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(_me_payload(request))


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(request=s.PasswordChangeSerializer, responses={204: None}, tags=["auth"])
    def post(self, request):
        ser = s.PasswordChangeSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user: User = request.user
        current = ser.validated_data.get("current_password", "")
        if user.has_usable_password() and not user.check_password(current):
            raise ApiError("Your current password is incorrect.", code="invalid_credentials", status_code=400)
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        # Keep this session, invalidate every other one.
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, user)
        audit.record("auth.password_changed", actor=user, target_type="user", target_id=user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Email ownership verification --------------------------------------------------------------------------
class EmailVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "otp"

    @extend_schema(request=None, responses={202: dict}, tags=["auth"])
    def post(self, request):
        if request.user.is_email_verified:
            return Response({"status": "already_verified"})
        result = services.send_email_verification(request.user)
        return Response({"status": "sent", "email": _email_payload(result)}, status=status.HTTP_202_ACCEPTED)


class EmailVerificationConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.TokenSerializer, responses={200: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.TokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = services.confirm_email_verification(ser.validated_data["token"])
        return Response({"status": "verified", "email": user.email})


# --- Passwordless (email OTP) sign-in ------------------------------------------------------------------------
class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    @extend_schema(request=s.EmailSerializer, responses={202: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.EmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=ser.validated_data["email"], is_active=True).first()
        delivery_mode = getattr(settings, "EMAIL_DELIVERY_MODE", "disabled")
        if user is not None:
            try:
                issued = services.issue_code(user, OneTimeCodePurpose.LOGIN)
                delivery_mode = issued.email.mode
            except ApiError as exc:
                # Rate-limit the issue, but do not change the response shape (account enumeration).
                if exc.error_code != "rate_limited":
                    raise
        # Identical response whether or not the account exists.
        return Response(
            {
                "status": "sent_if_account_exists",
                "delivery_mode": delivery_mode,
                "ttl_seconds": settings.OTP_TTL_SECONDS,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.OtpVerifySerializer, responses={200: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.OtpVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=ser.validated_data["email"], is_active=True).first()
        if user is None:
            raise ApiError(
                "That code is invalid or has expired. Request a new one.", code="invalid_code", status_code=400
            )
        services.verify_code(user, OneTimeCodePurpose.LOGIN, ser.validated_data["code"])
        services.mark_email_verified(user)
        # An emailed code was just completed for this sign-in, so the emailed second factor is satisfied too.
        _complete_login(request, user, second_factor_done=True)
        return Response({"status": "authenticated", **_me_payload(request)})


# --- Second factor (policy-controlled) ---------------------------------------------------------------------------
def _second_factor_subject(request) -> User:
    if request.user.is_authenticated:
        return request.user
    pending = request.session.get(PENDING_2FA_KEY)
    user = User.objects.filter(id=pending, is_active=True).first() if pending else None
    if user is None:
        raise ApiError("Sign in again to continue.", code="not_authenticated", status_code=401)
    return user


class SecondFactorRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp"

    @extend_schema(request=None, responses={202: dict}, tags=["auth"])
    def post(self, request):
        user = _second_factor_subject(request)
        issued = services.issue_code(user, OneTimeCodePurpose.SECOND_FACTOR)
        return Response(
            {"status": "sent", "email": _email_payload(issued.email), "expires_at": issued.expires_at},
            status=status.HTTP_202_ACCEPTED,
        )


class SecondFactorVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.CodeSerializer, responses={200: dict}, tags=["auth"])
    def post(self, request):
        ser = s.CodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = _second_factor_subject(request)
        services.verify_code(user, OneTimeCodePurpose.SECOND_FACTOR, ser.validated_data["code"])
        services.mark_email_verified(user)
        if request.user.is_authenticated:
            request.session[SESSION_SECOND_FACTOR_KEY] = int(time.time())
            audit.record("auth.second_factor_completed", actor=user, target_type="user", target_id=user.id)
        else:
            _complete_login(request, user, second_factor_done=True)
        return Response({"status": "authenticated", **_me_payload(request)})


# --- Password recovery --------------------------------------------------------------------------------------------
class PasswordForgotView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(request=s.EmailSerializer, responses={202: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.EmailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = services.send_password_reset(ser.validated_data["email"])
        mode = result.mode if result else getattr(settings, "EMAIL_DELIVERY_MODE", "disabled")
        return Response({"status": "sent_if_account_exists", "delivery_mode": mode}, status=status.HTTP_202_ACCEPTED)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=s.PasswordResetSerializer, responses={200: dict}, tags=["auth"], auth=[])
    def post(self, request):
        ser = s.PasswordResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.reset_password(**ser.validated_data)
        return Response({"status": "password_reset"})


# --- Google OAuth -----------------------------------------------------------------------------------------------------
class GoogleStartView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(responses={302: None}, tags=["auth"], auth=[])
    def get(self, request):
        if not services.google_enabled():
            raise ApiError("Google sign-in is not configured.", code="not_configured", status_code=404)
        url, state, verifier = services.google_authorization_url()
        request.session[OAUTH_STATE_KEY] = state
        request.session[OAUTH_VERIFIER_KEY] = verifier
        return HttpResponseRedirect(url)


class GoogleCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(responses={302: None}, tags=["auth"], auth=[])
    def get(self, request):
        if not services.google_enabled():
            raise ApiError("Google sign-in is not configured.", code="not_configured", status_code=404)
        expected_state = request.session.pop(OAUTH_STATE_KEY, "")
        verifier = request.session.pop(OAUTH_VERIFIER_KEY, "")
        error = request.GET.get("error")
        if error:
            return HttpResponseRedirect(f"{settings.FRONTEND_URL}/login?error=google_denied")
        try:
            identity = services.google_exchange(
                code=request.GET.get("code", ""),
                state=request.GET.get("state", ""),
                expected_state=expected_state,
                code_verifier=verifier,
            )
            user = services.user_from_google(identity)
        except ApiError as exc:
            return HttpResponseRedirect(f"{settings.FRONTEND_URL}/login?error={exc.error_code}")
        _complete_login(request, user, second_factor_done=False)
        # Redirect destinations are fixed server-side; nothing from the query string is used.
        destination = "/verify" if not second_factor_satisfied(request) else "/app"
        if not second_factor_satisfied(request):
            services.issue_code(user, OneTimeCodePurpose.SECOND_FACTOR)
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}{destination}")


# --- Super administrator -----------------------------------------------------------------------------------------------
class SecurityPolicyView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(responses={200: s.SecurityPolicySerializer}, tags=["admin"])
    def get(self, request):
        return Response(s.SecurityPolicySerializer(SecurityPolicy.load()).data)

    @extend_schema(request=s.SecurityPolicySerializer, responses={200: s.SecurityPolicySerializer}, tags=["admin"])
    def patch(self, request):
        policy = SecurityPolicy.load()
        before = policy.require_second_factor
        ser = s.SecurityPolicySerializer(policy, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(updated_by=request.user)
        audit.record(
            "admin.security_policy_updated",
            actor=request.user,
            target_type="security_policy",
            target_id=policy.id,
            metadata={"require_second_factor": {"from": before, "to": policy.require_second_factor}},
        )
        return Response(s.SecurityPolicySerializer(policy).data)


class AdminUsersView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(responses={200: s.AdminUserSerializer(many=True)}, tags=["admin"])
    def get(self, request):
        qs = User.objects.select_related("merchant").order_by("-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(s.AdminUserSerializer(page, many=True).data)


class AdminAuditView(APIView):
    permission_classes = [IsSuperAdmin]

    @extend_schema(responses={200: dict}, tags=["admin"])
    def get(self, request):
        qs = AuditEvent.objects.select_related("actor").order_by("-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [
            {
                "id": str(e.id),
                "action": e.action,
                "actor_email": e.actor.email if e.actor else None,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "metadata": e.metadata,
                "created_at": e.created_at,
            }
            for e in page
        ]
        return paginator.get_paginated_response(data)
