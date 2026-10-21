"""Authentication business logic. Views call these; nothing here touches request parsing."""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import OneTimeCode, OneTimeCodePurpose, Role, User
from apps.audit import services as audit
from apps.core.email import EmailResult, send_email
from apps.core.exceptions import ApiError
from apps.merchants.models import Merchant

logger = logging.getLogger("paypilot.auth")

EMAIL_VERIFY_SALT = "paypilot.email-verify"


# --- Registration ---------------------------------------------------------------------------
@transaction.atomic
def register_merchant(*, email: str, full_name: str, password: str | None) -> User:
    email = User.objects.normalize_email(email).lower()
    if User.objects.filter(email__iexact=email).exists():
        # Same response shape as success to avoid account enumeration; the view sends a notice email.
        raise ApiError("An account with this email may already exist.", code="email_in_use", status_code=409)
    user = User.objects.create_user(email=email, password=password, full_name=full_name.strip())
    Merchant.objects.create(user=user)
    audit.record("auth.register", actor=user, target_type="user", target_id=user.id)
    return user


# --- Password login with lockout ---------------------------------------------------------------
def _lockout_key(email: str, ip: str) -> str:
    digest = hashlib.sha256(f"{email.lower()}|{ip}".encode()).hexdigest()[:32]
    return f"login-fail:{digest}"


def is_locked_out(email: str, ip: str) -> bool:
    return (cache.get(_lockout_key(email, ip)) or 0) >= settings.LOGIN_MAX_FAILED_ATTEMPTS


def record_login_failure(email: str, ip: str) -> None:
    key = _lockout_key(email, ip)
    # add() is a no-op when the key exists, so the TTL is only set once per window.
    cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=settings.LOGIN_LOCKOUT_SECONDS)


def clear_login_failures(email: str, ip: str) -> None:
    cache.delete(_lockout_key(email, ip))


def authenticate_password(*, request, email: str, password: str, ip: str) -> User:
    if is_locked_out(email, ip):
        raise ApiError(
            "Too many failed sign-in attempts. Try again later or reset your password.",
            code="locked_out",
            status_code=429,
        )
    user = authenticate(request, username=email.lower(), password=password)
    if user is None or not user.is_active:
        record_login_failure(email, ip)
        audit.record("auth.login_failed", metadata={"email_domain": email.rsplit("@", 1)[-1] if "@" in email else ""})
        raise ApiError("Incorrect email or password.", code="invalid_credentials", status_code=401)
    clear_login_failures(email, ip)
    return user


# --- One-time codes -------------------------------------------------------------------------------
@dataclass(frozen=True)
class IssuedCode:
    code_id: str
    email: EmailResult
    expires_at: timezone.datetime


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_code(user: User, purpose: str) -> IssuedCode:
    """Create a fresh code (invalidating earlier unused ones) and email it. Rate-limited per user."""
    window_start = timezone.now() - timedelta(hours=1)
    issued_recently = OneTimeCode.objects.filter(user=user, purpose=purpose, created_at__gte=window_start).count()
    if issued_recently >= settings.OTP_MAX_ISSUES_PER_HOUR:
        raise ApiError(
            "Too many codes requested. Please wait before trying again.", code="rate_limited", status_code=429
        )

    OneTimeCode.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(consumed_at=timezone.now())
    code = _generate_code()
    expires_at = timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS)
    record = OneTimeCode.objects.create(
        user=user, purpose=purpose, code_hash=make_password(code), expires_at=expires_at
    )
    minutes = max(1, settings.OTP_TTL_SECONDS // 60)
    what = "sign in to" if purpose == OneTimeCodePurpose.LOGIN else "verify your sign-in to"
    result = send_email(
        to=user.email,
        subject=f"{code} is your PayPilot verification code",
        body=(
            f"Use this code to {what} PayPilot: {code}\n\n"
            f"It expires in {minutes} minutes. If you did not request it, you can ignore this email."
        ),
    )
    audit.record("auth.otp_issued", actor=user, target_type="otp", target_id=record.id, metadata={"purpose": purpose})
    return IssuedCode(code_id=str(record.id), email=result, expires_at=expires_at)


def verify_code(user: User, purpose: str, code: str) -> None:
    """Consume a code or raise. The attempt counter is committed before any error is raised,
    so a raised ApiError cannot roll the counter back."""
    now = timezone.now()
    outcome = "invalid"
    record_id = ""
    with transaction.atomic():
        record = (
            OneTimeCode.objects.select_for_update()
            .filter(user=user, purpose=purpose, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if record is None or record.expires_at <= now:
            outcome = "missing"
        elif record.attempts >= settings.OTP_MAX_ATTEMPTS:
            record.consumed_at = now
            record.save(update_fields=["consumed_at"])
            outcome = "exceeded"
            record_id = str(record.id)
        else:
            record.attempts += 1
            record.save(update_fields=["attempts"])
            record_id = str(record.id)
            if check_password(code.strip(), record.code_hash):
                record.consumed_at = now
                record.save(update_fields=["consumed_at"])
                outcome = "ok"
            elif record.attempts >= settings.OTP_MAX_ATTEMPTS:
                record.consumed_at = now
                record.save(update_fields=["consumed_at"])
                outcome = "exceeded"

    if outcome == "ok":
        audit.record(
            "auth.otp_verified", actor=user, target_type="otp", target_id=record_id, metadata={"purpose": purpose}
        )
        return
    if record_id:
        audit.record("auth.otp_failed", actor=user, target_type="otp", target_id=record_id)
    if outcome == "exceeded":
        raise ApiError(
            "Too many incorrect attempts. Request a new code.", code="code_attempts_exceeded", status_code=400
        )
    raise ApiError("That code is invalid or has expired. Request a new one.", code="invalid_code", status_code=400)


# --- Email ownership verification ---------------------------------------------------------------------
def make_email_verification_token(user: User) -> str:
    return signing.dumps({"u": str(user.id), "e": user.email}, salt=EMAIL_VERIFY_SALT)


def send_email_verification(user: User) -> EmailResult:
    token = make_email_verification_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    hours = settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS // 3600
    return send_email(
        to=user.email,
        subject="Confirm your email for PayPilot",
        body=f"Confirm that this address belongs to you by opening:\n\n{link}\n\nThe link expires in {hours} hours.",
    )


def confirm_email_verification(token: str) -> User:
    try:
        data = signing.loads(token, salt=EMAIL_VERIFY_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE_SECONDS)
        user = User.objects.get(id=data["u"], email=data["e"])
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError, ValueError):
        raise ApiError("This verification link is invalid or has expired.", code="invalid_token", status_code=400)
    mark_email_verified(user)
    return user


def mark_email_verified(user: User) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
        audit.record("auth.email_verified", actor=user, target_type="user", target_id=user.id)


# --- Password recovery ----------------------------------------------------------------------------------
def send_password_reset(email: str) -> EmailResult | None:
    """Returns None when no such active user exists; the view's response is identical either way."""
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not user.has_usable_password():
        return None
    uid = urlsafe_base64_encode(str(user.pk).encode())
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    audit.record("auth.password_reset_requested", actor=user, target_type="user", target_id=user.id)
    return send_email(
        to=user.email,
        subject="Reset your PayPilot password",
        body=f"Open this link to choose a new password:\n\n{link}\n\nIt expires in {minutes} minutes.",
    )


def reset_password(*, uid: str, token: str, new_password: str) -> User:
    invalid = ApiError("This reset link is invalid or has expired.", code="invalid_token", status_code=400)
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uid).decode())
    except (User.DoesNotExist, ValueError, TypeError, UnicodeDecodeError):
        raise invalid
    if not default_token_generator.check_token(user, token):
        raise invalid
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    mark_email_verified(user)
    audit.record("auth.password_reset", actor=user, target_type="user", target_id=user.id)
    return user


# --- Google OAuth ----------------------------------------------------------------------------------------
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL, not a secret
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def google_enabled() -> bool:
    return bool(
        settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET and settings.GOOGLE_OAUTH_REDIRECT_URI
    )


def _google_session(state: str | None = None, code_verifier: str | None = None):
    from authlib.integrations.requests_client import OAuth2Session

    return OAuth2Session(
        settings.GOOGLE_OAUTH_CLIENT_ID,
        settings.GOOGLE_OAUTH_CLIENT_SECRET,
        scope="openid email profile",
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
        state=state,
        code_challenge_method="S256",
        code_verifier=code_verifier,
    )


def google_authorization_url() -> tuple[str, str, str]:
    """Returns (url, state, code_verifier). State and verifier must be kept server-side (session)."""
    code_verifier = secrets.token_urlsafe(48)
    session = _google_session(code_verifier=code_verifier)
    url, state = session.create_authorization_url(GOOGLE_AUTHORIZE_URL, prompt="select_account")
    return url, state, code_verifier


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    full_name: str
    email_verified: bool


def google_exchange(*, code: str, state: str, expected_state: str, code_verifier: str) -> GoogleIdentity:
    if not state or not secrets.compare_digest(state, expected_state):
        raise ApiError("Sign-in could not be verified. Please try again.", code="oauth_state_mismatch", status_code=400)
    session = _google_session(state=state, code_verifier=code_verifier)
    try:
        session.fetch_token(GOOGLE_TOKEN_URL, code=code, timeout=10)
        info = session.get(GOOGLE_USERINFO_URL, timeout=10).json()
    except Exception:  # noqa: BLE001 - never leak provider internals
        logger.exception("google_oauth_exchange_failed")
        raise ApiError("Google sign-in failed. Please try again.", code="oauth_failed", status_code=502)
    email = str(info.get("email") or "").lower()
    if not email:
        raise ApiError("Google did not return an email address.", code="oauth_failed", status_code=502)
    return GoogleIdentity(
        email=email, full_name=str(info.get("name") or ""), email_verified=bool(info.get("email_verified"))
    )


@transaction.atomic
def user_from_google(identity: GoogleIdentity) -> User:
    if not identity.email_verified:
        raise ApiError("Your Google account email is not verified.", code="oauth_email_unverified", status_code=400)
    user = User.objects.filter(email__iexact=identity.email).first()
    if user is None:
        user = User.objects.create_user(email=identity.email, password=None, full_name=identity.full_name)
        Merchant.objects.create(user=user)
        audit.record("auth.register", actor=user, target_type="user", target_id=user.id, metadata={"via": "google"})
    if not user.is_active:
        raise ApiError("This account is disabled.", code="account_disabled", status_code=403)
    mark_email_verified(user)
    return user


def ensure_merchant(user: User) -> None:
    if user.role == Role.MERCHANT and not hasattr(user, "merchant"):
        Merchant.objects.create(user=user)
