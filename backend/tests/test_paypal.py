"""Phase 02: PayPal client, sync idempotency, errors, merchant isolation."""

from __future__ import annotations

import pytest
import responses
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.integrations.paypal_client import SANDBOX_HOST

PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture(autouse=True)
def _clear_paypal_cache():
    cache.clear()
    yield
    cache.clear()


def _merchant_client(email="seller@example.com") -> tuple[APIClient, User]:
    client = APIClient()
    res = client.post(
        "/api/auth/register/",
        {"email": email, "full_name": "Seller", "password": PASSWORD},
    )
    assert res.status_code == 201
    return client, User.objects.get(email=email)


def _token_ok():
    responses.add(
        responses.POST,
        f"{SANDBOX_HOST}/v1/oauth2/token",
        json={"access_token": "TESTTOKEN", "expires_in": 30000, "token_type": "Bearer"},
        status=200,
    )


def _txn(txn_id="TX-1", status="S", value="10.00", currency="USD"):
    return {
        "transaction_info": {
            "transaction_id": txn_id,
            "transaction_status": status,
            "transaction_event_code": "T0006",
            "transaction_amount": {"currency_code": currency, "value": value},
            "transaction_initiation_date": "2026-01-15T12:00:00+0000",
        },
        "payer_info": {"email_address": "buyer@example.com"},
    }


@pytest.mark.django_db
class TestMissingAndInvalidCredentials:
    def test_status_is_not_configured_without_credentials(self):
        client, _ = _merchant_client()
        res = client.get("/api/integrations/paypal/")
        assert res.status_code == 200
        assert res.json()["state"] == "not_configured"
        assert res.json()["state"] != "connected"

    def test_sync_without_credentials_is_honest(self):
        client, _ = _merchant_client()
        res = client.post("/api/integrations/paypal/sync/")
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "not_configured"

    @responses.activate
    def test_invalid_credentials(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        responses.add(responses.POST, f"{SANDBOX_HOST}/v1/oauth2/token", json={"error": "invalid_client"}, status=401)
        client, _ = _merchant_client()
        res = client.post("/api/integrations/paypal/verify/")
        assert res.status_code == 502
        assert res.json()["error"]["code"] == "invalid_credentials"
        status = client.get("/api/integrations/paypal/").json()
        assert status["state"] == "error"
        assert status["last_error_code"] == "invalid_credentials"


@pytest.mark.django_db
class TestSuccessfulSync:
    @responses.activate
    def test_imports_transactions_and_invoices_and_is_idempotent(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        settings.PAYPAL_SYNC_LOOKBACK_DAYS = 20
        _token_ok()
        responses.add(
            responses.GET,
            f"{SANDBOX_HOST}/v1/reporting/transactions",
            json={"transaction_details": [_txn(), _txn("TX-2", "P", "5.50", "EUR")], "total_pages": 1},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{SANDBOX_HOST}/v2/invoicing/invoices",
            json={
                "total_pages": 1,
                "items": [
                    {
                        "id": "INV2-AAA",
                        "status": "UNPAID",
                        "detail": {"invoice_number": "1001", "currency_code": "USD", "invoice_date": "2026-01-10"},
                        "amount": {"currency_code": "USD", "value": "80.00"},
                        "due_amount": {"currency_code": "USD", "value": "80.00"},
                    }
                ],
            },
            status=200,
        )
        client, user = _merchant_client()
        first = client.post("/api/integrations/paypal/sync/")
        assert first.status_code == 200, first.content
        body = first.json()
        assert body["connection"]["state"] == "connected"
        assert body["transactions"]["stored"] == 2
        assert body["invoices"]["stored"] == 1
        assert PayPalTransaction.objects.filter(merchant=user.merchant, source_id="TX-1").exists()
        eur = PayPalTransaction.objects.get(source_id="TX-2")
        assert str(eur.amount) == "5.50"
        assert eur.currency == "EUR"
        assert eur.status == "P"

        second = client.post("/api/integrations/paypal/sync/")
        assert second.status_code == 200
        assert second.json()["transactions"]["created"] == 0
        assert PayPalTransaction.objects.filter(merchant=user.merchant).count() == 2
        assert PayPalInvoice.objects.filter(merchant=user.merchant).count() == 1

        listing = client.get("/api/integrations/paypal/transactions/")
        assert listing.status_code == 200
        ids = {row["source_id"] for row in listing.json()["results"]}
        assert ids == {"TX-1", "TX-2"}

    @responses.activate
    def test_pagination_is_followed(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        settings.PAYPAL_SYNC_LOOKBACK_DAYS = 10
        _token_ok()
        responses.add(
            responses.GET,
            f"{SANDBOX_HOST}/v1/reporting/transactions",
            json={"transaction_details": [_txn("TX-A")], "total_pages": 2, "page": 1},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{SANDBOX_HOST}/v1/reporting/transactions",
            json={"transaction_details": [_txn("TX-B")], "total_pages": 2, "page": 2},
            status=200,
        )
        responses.add(
            responses.GET, f"{SANDBOX_HOST}/v2/invoicing/invoices", json={"items": [], "total_pages": 1}, status=200
        )
        client, user = _merchant_client()
        client.post("/api/integrations/paypal/sync/")
        assert PayPalTransaction.objects.filter(merchant=user.merchant).count() == 2


@pytest.mark.django_db
class TestPayPalErrors:
    @responses.activate
    def test_permission_error_on_transaction_search(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        settings.PAYPAL_SYNC_LOOKBACK_DAYS = 10
        _token_ok()
        responses.add(
            responses.GET, f"{SANDBOX_HOST}/v1/reporting/transactions", json={"name": "NOT_AUTHORIZED"}, status=403
        )
        responses.add(
            responses.GET,
            f"{SANDBOX_HOST}/v2/invoicing/invoices",
            json={"items": [], "total_pages": 1},
            status=200,
        )
        client, _ = _merchant_client()
        res = client.post("/api/integrations/paypal/sync/")
        assert res.status_code == 200
        assert res.json()["capabilities"]["transactions"] is False
        assert res.json()["capabilities"]["invoices"] is True
        assert res.json()["connection"]["state"] == "limited"

    @responses.activate
    def test_timeout(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        settings.PAYPAL_MAX_RETRIES = 0
        import requests as req

        responses.add(responses.POST, f"{SANDBOX_HOST}/v1/oauth2/token", body=req.Timeout())
        client, _ = _merchant_client()
        res = client.post("/api/integrations/paypal/verify/")
        assert res.status_code == 504
        assert res.json()["error"]["code"] == "paypal_timeout"


@pytest.mark.django_db
class TestIsolation:
    def test_merchant_cannot_read_another_merchants_transaction(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        a, user_a = _merchant_client("a@example.com")
        b, user_b = _merchant_client("b@example.com")
        txn = PayPalTransaction.objects.create(
            merchant=user_a.merchant, source_id="TX-SECRET", status="S", amount="9.00", currency="USD"
        )
        res = b.get(f"/api/integrations/paypal/transactions/{txn.id}/")
        assert res.status_code == 404
        assert a.get(f"/api/integrations/paypal/transactions/{txn.id}/").status_code == 200
        assert b.get("/api/integrations/paypal/transactions/").json()["results"] == []


@pytest.mark.live
@pytest.mark.django_db
def test_live_sandbox_token_if_credentials_present(settings):
    """Only runs when real sandbox credentials are exported. Never claimed as passed if skipped."""
    import os

    cid = os.environ.get("PAYPAL_LIVE_TEST_CLIENT_ID") or ""
    secret = os.environ.get("PAYPAL_LIVE_TEST_CLIENT_SECRET") or ""
    if not cid or not secret:
        pytest.skip("No live sandbox credentials in PAYPAL_LIVE_TEST_CLIENT_ID/SECRET")
    settings.PAYPAL_CLIENT_ID = cid
    settings.PAYPAL_CLIENT_SECRET = secret
    from apps.integrations.paypal_client import fetch_access_token

    token = fetch_access_token()
    assert token
