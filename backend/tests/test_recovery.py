"""Phase 04: recovery queue, ranking, approval, execution, isolation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import responses
from rest_framework.test import APIClient

from apps.accounts.services import register_merchant
from apps.agent.tools import execute_tool
from apps.audit.models import AuditEvent
from apps.integrations.models import PayPalInvoice
from apps.integrations.paypal_client import SANDBOX_HOST
from apps.recovery.models import ActionState, RecoveryAction, RecoveryCase, WorkflowStatus
from apps.recovery.priority import explanation, score
from apps.recovery.services import refresh_cases

PASSWORD = "Correct-Horse-Battery-9"


def _seller(email="seller@example.com"):
    user = register_merchant(email=email, full_name="Seller", password=PASSWORD)
    client = APIClient()
    client.force_login(user)
    return client, user


def _invoice(merchant, source="INV-1", status="SENT", due="40.00", currency="USD", **extra):
    defaults = {
        "merchant": merchant,
        "source_id": source,
        "invoice_number": source,
        "status": status,
        "amount": Decimal(due),
        "due_amount": Decimal(due),
        "currency": currency,
        "due_date": date(2026, 10, 1),
        "recipient_email": "buyer@example.com",
    }
    defaults.update(extra)
    return PayPalInvoice.objects.create(**defaults)


@pytest.mark.django_db
class TestQueueAndPriority:
    def test_outstanding_invoices_become_cases_without_invented_dates(self):
        client, user = _seller()
        _invoice(user.merchant, due_date=None, recipient_email="")
        PayPalInvoice.objects.create(
            merchant=user.merchant,
            source_id="PAID-1",
            status="PAID",
            amount=Decimal("9.00"),
            due_amount=Decimal("0.00"),
            currency="USD",
        )
        res = client.get("/api/recovery/")
        assert res.status_code == 200
        rows = res.json()["results"]
        assert len(rows) == 1
        row = rows[0]
        assert row["due_date_available"] is False
        assert row["days_overdue"] is None
        assert row["recipient_available"] is False
        assert "no due date is available" in row["priority_explanation"]

    def test_ranking_prefers_overdue_amount_and_is_explainable(self):
        _, user = _seller()
        old = _invoice(user.merchant, source="OLD", due="10.00", due_date=date(2026, 9, 1))
        new = _invoice(user.merchant, source="NEW", due="500.00", due_date=date(2026, 10, 20))
        refresh_cases(user.merchant)
        today = date(2026, 10, 21)
        older = RecoveryCase.objects.get(invoice=old)
        newer = RecoveryCase.objects.get(invoice=new)
        assert score(older, today=today) > score(newer, today=today)
        text = explanation(older, today=today)
        assert "50 days overdue" in text
        assert "10.00 USD" in text
        assert "likely" not in text.lower()

    def test_metrics_do_not_treat_a_reminder_as_recovered(self):
        client, user = _seller()
        _invoice(user.merchant)
        queue = client.get("/api/recovery/").json()
        assert queue["metrics"]["reminders_successfully_sent"] == 0
        assert queue["metrics"]["payments_subsequently_confirmed"] == []
        identified = {row["currency"]: row["amount"] for row in queue["metrics"]["outstanding_identified"]}
        assert identified["USD"] == "40.00"


@pytest.mark.django_db
class TestApprovalAndExecution:
    def _draft(self, client):
        case_id = client.get("/api/recovery/").json()["results"][0]["id"]
        draft = client.post(f"/api/recovery/cases/{case_id}/draft/", {})
        assert draft.status_code == 200
        return case_id, draft.json()["id"]

    def test_copy_path_requires_confirm_and_records_copied_not_sent(self):
        client, user = _seller()
        _invoice(user.merchant)
        _, action_id = self._draft(client)
        assert client.post(f"/api/recovery/actions/{action_id}/submit/", {"delivery": "copy"}).status_code == 200
        denied = client.post(f"/api/recovery/actions/{action_id}/approve/", {"confirm": False})
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "approval_required"
        assert client.post(f"/api/recovery/actions/{action_id}/approve/", {"confirm": True}).status_code == 200
        executed = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "copy-1"},
        )
        assert executed.status_code == 200
        body = executed.json()
        assert body["outcome"] == "copied"
        assert body["state"] == ActionState.ACTION_COMPLETED
        metrics = client.get("/api/recovery/").json()["metrics"]
        assert metrics["reminders_successfully_sent"] == 0
        assert AuditEvent.objects.filter(action="recovery.executed", merchant=user.merchant).exists()

    def test_execute_without_approval_is_rejected(self):
        client, user = _seller()
        _invoice(user.merchant)
        _, action_id = self._draft(client)
        res = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "nope"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "approval_required"

    def test_duplicate_in_flight_action_is_blocked(self):
        client, user = _seller()
        _invoice(user.merchant)
        case_id, _ = self._draft(client)
        again = client.post(f"/api/recovery/cases/{case_id}/draft/", {})
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "duplicate_action"

    def test_idempotent_execute_does_not_send_twice(self):
        client, user = _seller()
        _invoice(user.merchant)
        _, action_id = self._draft(client)
        client.post(f"/api/recovery/actions/{action_id}/submit/", {"delivery": "copy"})
        client.post(f"/api/recovery/actions/{action_id}/approve/", {"confirm": True})
        first = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "same-key"},
        )
        second = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "same-key"},
        )
        assert first.status_code == 200
        assert second.status_code == 409
        assert RecoveryAction.objects.filter(merchant=user.merchant, outcome="copied").count() == 1

    def test_email_without_smtp_stays_failed(self, settings):
        settings.EMAIL_DELIVERY_MODE = "disabled"
        client, user = _seller()
        _invoice(user.merchant)
        _, action_id = self._draft(client)
        client.post(f"/api/recovery/actions/{action_id}/submit/", {"delivery": "email"})
        client.post(f"/api/recovery/actions/{action_id}/approve/", {"confirm": True})
        res = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "email-1"},
        )
        assert res.status_code == 503
        action = RecoveryAction.objects.get(pk=action_id)
        assert action.state == ActionState.FAILED
        assert action.outcome == "email_not_delivered"

    @responses.activate
    def test_paypal_remind_succeeds_only_on_204(self, settings):
        settings.PAYPAL_CLIENT_ID = "id"
        settings.PAYPAL_CLIENT_SECRET = "secret"
        responses.add(responses.POST, f"{SANDBOX_HOST}/v1/oauth2/token", json={"access_token": "T", "expires_in": 3000})
        responses.add(responses.POST, f"{SANDBOX_HOST}/v2/invoicing/invoices/INV-1/remind", status=204)
        client, user = _seller()
        _invoice(user.merchant)
        _, action_id = self._draft(client)
        client.post(f"/api/recovery/actions/{action_id}/submit/", {"delivery": "paypal_remind"})
        client.post(f"/api/recovery/actions/{action_id}/approve/", {"confirm": True})
        res = client.post(
            f"/api/recovery/actions/{action_id}/execute/",
            {"confirm": True, "idempotency_key": "pp-1"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["outcome"] == "paypal_reminded"
        assert body["paypal_http_status"] == 204
        assert client.get("/api/recovery/").json()["metrics"]["reminders_successfully_sent"] == 1

    def test_invalid_transition_is_rejected(self):
        _, user = _seller()
        _invoice(user.merchant)
        refresh_cases(user.merchant)
        case = RecoveryCase.objects.get(merchant=user.merchant)
        from apps.core.exceptions import ApiError
        from apps.recovery.services import _transition

        with pytest.raises(ApiError) as exc:
            _transition(case, WorkflowStatus.EXECUTING)
        assert exc.value.error_code == "invalid_state"


@pytest.mark.django_db
class TestIsolationAndTools:
    def test_other_merchant_cannot_see_or_act(self):
        client_a, a = _seller("a@example.com")
        client_b, _b = _seller("b@example.com")
        _invoice(a.merchant)
        case_id = client_a.get("/api/recovery/").json()["results"][0]["id"]
        assert client_b.get(f"/api/recovery/cases/{case_id}/").status_code == 404
        assert client_b.post(f"/api/recovery/cases/{case_id}/draft/", {}).status_code == 404
        assert client_b.get("/api/recovery/").json()["results"] == []

    def test_assistant_can_draft_but_not_send(self):
        _, user = _seller()
        invoice = _invoice(user.merchant)
        refresh_cases(user.merchant)
        drafted = execute_tool(user.merchant, "draft_payment_reminder", f'{{"invoice_id":"{invoice.id}"}}')
        assert drafted["sent"] is False
        assert drafted["draft"]["state"] == ActionState.DRAFT_PREPARED
        blocked = execute_tool(user.merchant, "send_invoice_reminder", "{}")
        assert blocked["error"] == "tool_not_allowed"
        queue = execute_tool(user.merchant, "list_recovery_queue", "{}")
        assert queue["count"] == 1
