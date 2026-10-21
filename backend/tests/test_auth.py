"""Phase 01: authentication, OTP, sessions, isolation, administrator policy."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import OneTimeCode, OneTimeCodePurpose, SecurityPolicy, User
from apps.accounts.services import make_email_verification_token, send_password_reset
from apps.audit.models import AuditEvent
from apps.core.logging import REDACTED
from apps.merchants.models import Merchant

PASSWORD = "Correct-Horse-Battery-9"
OTP_RE = re.compile(r"\b(\d{6})\b")


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _otp_from_mailbox() -> str:
    assert mail.outbox, "expected an email"
    match = OTP_RE.search(mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1)


def register(client, email="ada@example.com", **extra) -> APIClient:
    payload = {"email": email, "full_name": "Ada Lovelace", "password": PASSWORD, **extra}
    res = client.post("/api/auth/register/", payload)
    assert res.status_code == 201, res.content
    return client


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login/", {"email": email, "password": password})


@pytest.mark.django_db
class TestRegistrationAndSession:
    def test_register_creates_merchant_and_sets_http_only_session(self, client):
        res = client.post(
            "/api/auth/register/",
            {"email": "ada@example.com", "full_name": "Ada Lovelace", "password": PASSWORD},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["user"]["email"] == "ada@example.com"
        assert body["user"]["role"] == "merchant"
        assert body["merchant"]["onboarding_status"] == "new"
        assert PASSWORD not in str(body)
        assert "hashed" not in str(body).lower()
        assert User.objects.filter(email="ada@example.com").exists()
        assert Merchant.objects.filter(user__email="ada@example.com").exists()
        cookie = res.cookies.get("paypilot_session")
        assert cookie is not None
        assert cookie["httponly"] is True
        me = client.get("/api/auth/me/")
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "ada@example.com"

    def test_duplicate_email_is_rejected_and_does_not_leak_the_existing_password(self, client):
        register(client)
        other = APIClient()
        res = other.post(
            "/api/auth/register/",
            {"email": "ada@example.com", "full_name": "Other", "password": "Another-Valid-Password-1"},
        )
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "email_in_use"
        assert "password" not in res.content.decode().lower()

    def test_short_password_is_rejected_by_validators(self, client):
        res = client.post("/api/auth/register/", {"email": "b@c.co", "full_name": "B", "password": "short"})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
class TestPasswordLogin:
    def test_valid_credentials_establish_a_session(self, client):
        register(client)
        client.post("/api/auth/logout/")
        res = login(client, "ada@example.com")
        assert res.status_code == 200
        assert res.json()["status"] == "authenticated"
        assert client.get("/api/auth/me/").status_code == 200

    def test_invalid_credentials_are_rejected_without_enumeration(self, client):
        register(client)
        client.post("/api/auth/logout/")
        missing = login(client, "nobody@example.com", "Wrong-Password-99")
        wrong = login(client, "ada@example.com", "Wrong-Password-99")
        assert missing.status_code == wrong.status_code == 401
        assert missing.json()["error"]["code"] == wrong.json()["error"]["code"] == "invalid_credentials"

    def test_lockout_after_repeated_failures(self, client, settings):
        settings.LOGIN_MAX_FAILED_ATTEMPTS = 3
        register(client)
        client.post("/api/auth/logout/")
        for _ in range(3):
            login(client, "ada@example.com", "Wrong-Password-99")
        res = login(client, "ada@example.com", PASSWORD)
        assert res.status_code == 429
        assert res.json()["error"]["code"] == "locked_out"

    def test_logout_invalidates_the_session(self, client):
        register(client)
        assert client.get("/api/auth/me/").status_code == 200
        assert client.post("/api/auth/logout/").status_code == 204
        assert client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
class TestOtp:
    def test_passwordless_sign_in_and_email_ownership_verification(self, client):
        register(client)
        client.post("/api/auth/logout/")
        req = client.post("/api/auth/otp/request/", {"email": "ada@example.com"})
        assert req.status_code == 202
        code = _otp_from_mailbox()
        # The code must never appear in the API response.
        assert code not in req.content.decode()
        verify = client.post("/api/auth/otp/verify/", {"email": "ada@example.com", "code": code})
        assert verify.status_code == 200
        assert verify.json()["user"]["email_verified"] is True
        assert client.get("/api/auth/me/").status_code == 200

    def test_unknown_email_gets_the_same_otp_request_response(self, client):
        known = client.post("/api/auth/otp/request/", {"email": "ghost@example.com"})
        assert known.status_code == 202
        assert known.json()["status"] == "sent_if_account_exists"
        assert not mail.outbox

    def test_otp_expires(self, client):
        register(client)
        client.post("/api/auth/logout/")
        client.post("/api/auth/otp/request/", {"email": "ada@example.com"})
        code = _otp_from_mailbox()
        OneTimeCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        res = client.post("/api/auth/otp/verify/", {"email": "ada@example.com", "code": code})
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "invalid_code"

    def test_otp_attempt_limit(self, client, settings):
        settings.OTP_MAX_ATTEMPTS = 2
        register(client)
        client.post("/api/auth/logout/")
        client.post("/api/auth/otp/request/", {"email": "ada@example.com"})
        _otp_from_mailbox()
        first = client.post("/api/auth/otp/verify/", {"email": "ada@example.com", "code": "000000"})
        second = client.post("/api/auth/otp/verify/", {"email": "ada@example.com", "code": "000000"})
        assert first.json()["error"]["code"] == "invalid_code"
        assert second.json()["error"]["code"] == "code_attempts_exceeded"
        # The spent code cannot be reused, even with the real value.
        real = _otp_from_mailbox()
        reused = client.post("/api/auth/otp/verify/", {"email": "ada@example.com", "code": real})
        assert reused.json()["error"]["code"] == "invalid_code"

    def test_otp_issue_rate_limit(self, client, settings):
        settings.OTP_MAX_ISSUES_PER_HOUR = 2
        register(client)
        client.post("/api/auth/logout/")
        assert client.post("/api/auth/otp/request/", {"email": "ada@example.com"}).status_code == 202
        assert client.post("/api/auth/otp/request/", {"email": "ada@example.com"}).status_code == 202
        # Further requests stay 202 so existence cannot be inferred from the status code.
        res = client.post("/api/auth/otp/request/", {"email": "ada@example.com"})
        assert res.status_code == 202
        assert OneTimeCode.objects.filter(purpose=OneTimeCodePurpose.LOGIN).count() == 2


@pytest.mark.django_db
class TestEmailVerificationAndPasswordRecovery:
    def test_email_verification_link(self, client):
        register(client)
        user = User.objects.get(email="ada@example.com")
        assert user.email_verified_at is None
        token = make_email_verification_token(user)
        res = client.post("/api/auth/verify-email/", {"token": token})
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.email_verified_at is not None

    def test_password_reset_works_and_invalidates_the_old_password(self, client):
        register(client)
        client.post("/api/auth/logout/")
        forgot = client.post("/api/auth/password/forgot/", {"email": "ada@example.com"})
        assert forgot.status_code == 202
        body = mail.outbox[-1].body
        uid = re.search(r"uid=([^&]+)", body).group(1)
        token = re.search(r"token=(\S+)", body).group(1)
        assert uid not in forgot.content.decode() or "uid=" not in forgot.content.decode()
        reset = client.post(
            "/api/auth/password/reset/",
            {"uid": uid, "token": token, "new_password": "Brand-New-Password-42"},
        )
        assert reset.status_code == 200
        assert login(client, "ada@example.com", PASSWORD).status_code == 401
        assert login(client, "ada@example.com", "Brand-New-Password-42").status_code == 200

    def test_password_forgot_does_not_reveal_whether_the_account_exists(self, client):
        a = client.post("/api/auth/password/forgot/", {"email": "nobody@example.com"})
        register(APIClient())
        b = client.post("/api/auth/password/forgot/", {"email": "ada@example.com"})
        assert a.status_code == b.status_code == 202
        assert a.json()["status"] == b.json()["status"] == "sent_if_account_exists"


@pytest.mark.django_db
class TestSecondFactorPolicy:
    def test_policy_is_enforced_on_merchant_endpoints_and_logged(self, client):
        admin = User.objects.create_superuser(email="root@example.com", password=PASSWORD, full_name="Root")
        register(client, email="seller@example.com")
        admin_client = APIClient()
        assert admin_client.post("/api/auth/login/", {"email": admin.email, "password": PASSWORD}).status_code == 200
        # Merchants cannot change the policy.
        assert client.patch("/api/admin/security-policy/", {"require_second_factor": True}).status_code == 403
        res = admin_client.patch("/api/admin/security-policy/", {"require_second_factor": True})
        assert res.status_code == 200
        assert res.json()["require_second_factor"] is True
        assert AuditEvent.objects.filter(action="admin.security_policy_updated").exists()

        # Existing session now fails merchant-only endpoints until the emailed code is completed.
        blocked = client.get("/api/merchant/profile/")
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "second_factor_required"
        # /auth/me still works so the SPA can route to the challenge.
        me = client.get("/api/auth/me/")
        assert me.status_code == 200
        assert me.json()["second_factor_required"] is True

        client.post("/api/auth/second-factor/request/")
        code = _otp_from_mailbox()
        verify = client.post("/api/auth/second-factor/verify/", {"code": code})
        assert verify.status_code == 200
        assert verify.json()["second_factor_required"] is False
        assert client.get("/api/merchant/profile/").status_code == 200

    def test_password_login_parks_the_user_until_the_code_is_verified(self, client):
        SecurityPolicy.objects.create(id=1, require_second_factor=True)
        register(APIClient(), email="seller@example.com")
        fresh = APIClient()
        res = login(fresh, "seller@example.com")
        assert res.status_code == 200
        assert res.json()["status"] == "second_factor_required"
        assert fresh.get("/api/auth/me/").status_code == 401
        code = _otp_from_mailbox()
        assert "code" not in res.json()
        done = fresh.post("/api/auth/second-factor/verify/", {"code": code})
        assert done.status_code == 200
        assert done.json()["status"] == "authenticated"
        assert fresh.get("/api/merchant/profile/").status_code == 200

    def test_super_admin_is_not_subject_to_the_seller_second_factor(self, client):
        SecurityPolicy.objects.create(id=1, require_second_factor=True)
        User.objects.create_superuser(email="root@example.com", password=PASSWORD, full_name="Root")
        res = login(client, "root@example.com")
        assert res.status_code == 200
        assert res.json()["status"] == "authenticated"
        assert client.get("/api/admin/security-policy/").status_code == 200


@pytest.mark.django_db
class TestMerchantIsolation:
    def test_each_merchant_sees_only_their_own_profile(self):
        a, b = APIClient(), APIClient()
        register(a, email="a@example.com")
        register(b, email="b@example.com")
        a.patch("/api/merchant/profile/", {"business_name": "Ada Ltd", "country": "GB"})
        b.patch("/api/merchant/profile/", {"business_name": "Bob Ltd", "country": "US"})
        assert a.get("/api/merchant/profile/").json()["business_name"] == "Ada Ltd"
        assert b.get("/api/merchant/profile/").json()["business_name"] == "Bob Ltd"
        # A client-supplied merchant identifier is ignored.
        other_id = str(User.objects.get(email="b@example.com").merchant.id)
        sneak = a.patch("/api/merchant/profile/", {"id": other_id, "business_name": "Hijacked", "country": "GB"})
        assert sneak.status_code == 200
        assert sneak.json()["business_name"] == "Hijacked"
        assert b.get("/api/merchant/profile/").json()["business_name"] == "Bob Ltd"

    def test_merchants_cannot_reach_administrator_endpoints(self, client):
        register(client)
        assert client.get("/api/admin/users/").status_code == 403
        assert client.get("/api/admin/audit/").status_code == 403
        assert client.get("/api/admin/security-policy/").status_code == 403

    def test_super_admin_cannot_use_merchant_routes(self, client):
        User.objects.create_superuser(email="root@example.com", password=PASSWORD, full_name="Root")
        login(client, "root@example.com")
        res = client.get("/api/merchant/profile/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestCsrfAndGoogle:
    def test_unsafe_methods_require_csrf(self, csrf_client):
        register(APIClient())
        res = csrf_client.post("/api/auth/login/", {"email": "ada@example.com", "password": PASSWORD}, format="json")
        assert res.status_code == 403

    def test_google_start_is_hidden_when_unconfigured(self, client):
        res = client.get("/api/auth/google/start/")
        assert res.status_code == 404
        assert client.get("/api/auth/config/").json()["google_enabled"] is False

    def test_google_callback_rejects_a_mismatched_state(self, client, settings):
        settings.GOOGLE_OAUTH_CLIENT_ID = "id"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
        settings.GOOGLE_OAUTH_REDIRECT_URI = "http://localhost:5173/api/auth/google/callback/"
        client.get("/api/auth/csrf/")
        session = client.session
        session["google_oauth_state"] = "expected"
        session["google_oauth_verifier"] = "verifier"
        session.save()
        res = client.get("/api/auth/google/callback/?code=abc&state=forged")
        assert res.status_code == 302
        assert "oauth_state_mismatch" in res["Location"]


@pytest.mark.django_db
class TestSecretsStayHidden:
    def test_otp_and_tokens_are_never_in_json_or_audit_metadata(self, client):
        register(client)
        client.post("/api/auth/logout/")
        client.post("/api/auth/otp/request/", {"email": "ada@example.com"})
        code = _otp_from_mailbox()
        for event in AuditEvent.objects.all():
            blob = str(event.metadata)
            assert code not in blob
            assert PASSWORD not in blob
            assert "token" not in blob.lower() or REDACTED in blob or "token" not in event.metadata
        send_password_reset("ada@example.com")
        reset_mail = mail.outbox[-1].body
        assert "token=" in reset_mail
        # API responses for forgot/reset-request do not include the link.
        forgot = client.post("/api/auth/password/forgot/", {"email": "ada@example.com"})
        assert "token=" not in forgot.content.decode()
        assert "uid=" not in forgot.content.decode()
