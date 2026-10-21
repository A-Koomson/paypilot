"""Phase 05: matching, exceptions, isolation, auditability of resolutions."""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import register_merchant
from apps.audit.models import AuditEvent
from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.reconciliation.models import ReconciliationException, ResolutionEvent

PASSWORD = "Correct-Horse-Battery-9"


def _seller(email="seller@example.com"):
    user = register_merchant(email=email, full_name="Seller", password=PASSWORD)
    client = APIClient()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
class TestMatching:
    def test_identifier_match_and_unfulfilled_payment(self):
        client, user = _seller()
        PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="INV2-AAA",
            invoice_number="INV-100",
            status="PAID",
            amount=Decimal("25.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        created = client.post(
            "/api/reconciliation/orders/",
            {
                "internal_reference": "ORD-1",
                "external_reference": "INV-100",
                "amount": "25.00",
                "currency": "USD",
                "fulfillment_status": "unfulfilled",
            },
        )
        assert created.status_code == 201
        ran = client.post("/api/reconciliation/run/")
        assert ran.status_code == 200
        rows = client.get("/api/reconciliation/exceptions/").json()["results"]
        kinds = {row["kind"] for row in rows}
        assert "payment_unfulfilled" in kinds
        assert all(row["status"] == "open" for row in rows)

    def test_amount_mismatch_is_inconsistency_not_a_silent_match(self):
        client, user = _seller()
        PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="INV2-BBB",
            invoice_number="INV-200",
            status="PAID",
            amount=Decimal("25.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        client.post(
            "/api/reconciliation/orders/",
            {"internal_reference": "ORD-2", "external_reference": "INV-200", "amount": "30.00", "currency": "USD"},
        )
        client.post("/api/reconciliation/run/")
        kinds = {row["kind"] for row in client.get("/api/reconciliation/exceptions/").json()["results"]}
        assert "amount_mismatch" in kinds
        assert "payment_unfulfilled" not in kinds

    def test_amount_without_identifier_requires_review(self):
        client, user = _seller()
        PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="INV2-CCC",
            invoice_number="OTHER",
            status="SENT",
            amount=Decimal("12.00"),
            due_amount=Decimal("12.00"),
            currency="EUR",
        )
        client.post(
            "/api/reconciliation/orders/",
            {"internal_reference": "ORD-3", "amount": "12.00", "currency": "EUR"},
        )
        client.post("/api/reconciliation/run/")
        rows = client.get("/api/reconciliation/exceptions/?kind=missing_source").json()["results"]
        assert rows
        assert rows[0]["outcome"] == "requires_manual_review"

    def test_ambiguous_identifiers_are_not_auto_matched(self):
        client, user = _seller()
        PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="INV-X",
            invoice_number="SHARED",
            status="PAID",
            amount=Decimal("5.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        PayPalTransaction.objects.create(
            merchant=user.merchant,
            source_id="SHARED",
            status="S",
            amount=Decimal("5.00"),
            currency="USD",
        )
        client.post(
            "/api/reconciliation/orders/",
            {"internal_reference": "ORD-4", "external_reference": "SHARED", "amount": "5.00", "currency": "USD"},
        )
        client.post("/api/reconciliation/run/")
        kinds = {row["kind"] for row in client.get("/api/reconciliation/exceptions/").json()["results"]}
        assert "ambiguous" in kinds

    def test_resolution_is_auditable_and_does_not_change_paypal(self):
        client, user = _seller()
        invoice = PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="INV-KEEP",
            invoice_number="KEEP",
            status="PAID",
            amount=Decimal("8.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        client.post("/api/reconciliation/run/")
        exc_id = client.get("/api/reconciliation/exceptions/").json()["results"][0]["id"]
        resolved = client.post(
            f"/api/reconciliation/exceptions/{exc_id}/resolve/",
            {"resolution_code": "not_applicable", "note": "Internal bookkeeping only."},
        )
        assert resolved.status_code == 200
        invoice.refresh_from_db()
        assert invoice.status == "PAID"
        assert invoice.source_id == "INV-KEEP"
        assert ResolutionEvent.objects.filter(exception_id=exc_id, action="resolve").exists()
        assert AuditEvent.objects.filter(action="reconciliation.resolved", merchant=user.merchant).exists()
        reopened = client.post(f"/api/reconciliation/exceptions/{exc_id}/reopen/", {"note": "Need another look."})
        assert reopened.status_code == 200
        assert reopened.json()["status"] == "reopened"

    def test_cross_merchant_access_is_hidden(self):
        client_a, a = _seller("a@example.com")
        client_b, _b = _seller("b@example.com")
        PayPalInvoice.objects.create(
            merchant=a.merchant,
            source_id="PRIV",
            status="PAID",
            amount=Decimal("1.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        client_a.post("/api/reconciliation/run/")
        exc_id = client_a.get("/api/reconciliation/exceptions/").json()["results"][0]["id"]
        assert client_b.get(f"/api/reconciliation/exceptions/{exc_id}/").status_code == 404
        assert client_b.post(
            f"/api/reconciliation/exceptions/{exc_id}/resolve/",
            {"resolution_code": "not_applicable", "note": "x"},
        ).status_code == 404
        assert client_b.get("/api/reconciliation/exceptions/").json()["results"] == []
        assert ReconciliationException.objects.filter(merchant=a.merchant).exists()
