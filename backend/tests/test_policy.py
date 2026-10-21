"""Phase 06: central auth, idempotency, merchant audit, append-only history."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import register_merchant
from apps.audit.models import AuditEvent
from apps.audit.services import record
from apps.core.exceptions import ApiError
from apps.policy.authorization import authorize

PASSWORD = "Correct-Horse-Battery-9"


def _seller(email="seller@example.com"):
    user = register_merchant(email=email, full_name="S", password=PASSWORD)
    client = APIClient()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
class TestAuthorization:
    def test_unsupported_and_cross_tenant_are_denied(self):
        _, user = _seller()
        _, other = _seller("other@example.com")
        with pytest.raises(ApiError) as exc:
            authorize(user=user, merchant=user.merchant, action="refund.execute")
        assert exc.value.error_code == "unsupported_action"
        with pytest.raises(ApiError) as exc:
            authorize(user=user, merchant=other.merchant, action="recovery.execute", approved=True)
        assert exc.value.error_code == "not_found"
        with pytest.raises(ApiError) as exc:
            authorize(user=user, merchant=user.merchant, action="recovery.execute", approved=False)
        assert exc.value.error_code == "approval_required"


@pytest.mark.django_db
class TestAudit:
    def test_merchant_can_read_own_events_only(self):
        client_a, a = _seller("a@example.com")
        client_b, b = _seller("b@example.com")
        record("recovery.draft_prepared", actor=a, merchant=a.merchant, target_type="recovery_action", target_id="1")
        record("recovery.draft_prepared", actor=b, merchant=b.merchant, target_type="recovery_action", target_id="2")
        rows = client_a.get("/api/audit/").json()["results"]
        assert {row["target_id"] for row in rows} == {"1"}
        assert client_b.get("/api/audit/").json()["results"][0]["target_id"] == "2"

    def test_audit_and_resolution_history_are_append_only(self):
        _, user = _seller()
        event = record("agent.turn", actor=user, merchant=user.merchant)
        with pytest.raises(RuntimeError):
            event.save()
        with pytest.raises(RuntimeError):
            event.delete()
        assert AuditEvent.objects.filter(pk=event.pk).exists()

    def test_sensitive_keys_are_not_stored(self):
        _, user = _seller()
        event = record(
            "recovery.executed",
            actor=user,
            merchant=user.merchant,
            metadata={"token": "secret-value", "delivery": "copy"},
        )
        assert "secret-value" not in str(event.metadata)
        assert event.metadata["delivery"] == "copy"
