from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.integrations.models import PayPalInvoice
from apps.merchants.models import Merchant

CURRENCY = RegexValidator(r"^[A-Z]{3}$", "Use a three-letter ISO currency code.")


class WorkflowStatus(models.TextChoices):
    IDENTIFIED = "identified"
    NEEDS_REVIEW = "needs_review"
    DRAFT_PREPARED = "draft_prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    ACTION_COMPLETED = "action_completed"
    FAILED = "failed"
    RESOLVED = "resolved"


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    WorkflowStatus.IDENTIFIED: frozenset(
        {WorkflowStatus.NEEDS_REVIEW, WorkflowStatus.DRAFT_PREPARED, WorkflowStatus.RESOLVED}
    ),
    WorkflowStatus.NEEDS_REVIEW: frozenset(
        {WorkflowStatus.DRAFT_PREPARED, WorkflowStatus.RESOLVED, WorkflowStatus.IDENTIFIED}
    ),
    WorkflowStatus.DRAFT_PREPARED: frozenset({WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.NEEDS_REVIEW}),
    WorkflowStatus.AWAITING_APPROVAL: frozenset({WorkflowStatus.APPROVED, WorkflowStatus.NEEDS_REVIEW}),
    WorkflowStatus.APPROVED: frozenset({WorkflowStatus.EXECUTING, WorkflowStatus.NEEDS_REVIEW}),
    WorkflowStatus.EXECUTING: frozenset({WorkflowStatus.ACTION_COMPLETED, WorkflowStatus.FAILED}),
    WorkflowStatus.ACTION_COMPLETED: frozenset(
        {WorkflowStatus.RESOLVED, WorkflowStatus.IDENTIFIED, WorkflowStatus.NEEDS_REVIEW}
    ),
    WorkflowStatus.FAILED: frozenset({WorkflowStatus.NEEDS_REVIEW, WorkflowStatus.DRAFT_PREPARED}),
    WorkflowStatus.RESOLVED: frozenset({WorkflowStatus.IDENTIFIED, WorkflowStatus.NEEDS_REVIEW}),
}


class DeliveryChannel(models.TextChoices):
    COPY = "copy"
    EMAIL = "email"
    PAYPAL_REMIND = "paypal_remind"


class ActionState(models.TextChoices):
    DRAFT_PREPARED = "draft_prepared"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    ACTION_COMPLETED = "action_completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RecoveryCase(models.Model):
    """One outstanding imported invoice, with an explicit recovery workflow state."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="recovery_cases")
    invoice = models.ForeignKey(PayPalInvoice, on_delete=models.CASCADE, related_name="recovery_cases")
    workflow_status = models.CharField(max_length=32, choices=WorkflowStatus.choices, default=WorkflowStatus.IDENTIFIED)
    merchant_priority = models.PositiveSmallIntegerField(default=0)
    last_follow_up_at = models.DateTimeField(null=True, blank=True)
    identified_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "invoice"], name="recovery_case_invoice_unique"),
            models.CheckConstraint(
                condition=models.Q(workflow_status__in=WorkflowStatus.values),
                name="recovery_case_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["merchant", "workflow_status"]),
            models.Index(fields=["merchant", "-last_follow_up_at"]),
        ]

    def __str__(self) -> str:
        return f"RecoveryCase({self.invoice_id})"


class RecoveryAction(models.Model):
    """A reminder draft or execution attempt. Sending requires a later approval."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(RecoveryCase, on_delete=models.CASCADE, related_name="actions")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="recovery_actions")
    kind = models.CharField(max_length=16, default="remind")
    delivery = models.CharField(max_length=16, choices=DeliveryChannel.choices, default=DeliveryChannel.COPY)
    state = models.CharField(max_length=32, choices=ActionState.choices, default=ActionState.DRAFT_PREPARED)
    recipient_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    invoice_reference = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    delivery_disclosure = models.CharField(max_length=400, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    executed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=32, blank=True)
    outcome_detail = models.CharField(max_length=400, blank=True)
    paypal_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(kind="remind"), name="recovery_action_kind_valid"),
            models.CheckConstraint(
                condition=models.Q(state__in=ActionState.values),
                name="recovery_action_state_valid",
            ),
        ]
        indexes = [models.Index(fields=["merchant", "-created_at"]), models.Index(fields=["case", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"RecoveryAction({self.id})"
