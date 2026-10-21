from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.merchants.models import Merchant

CURRENCY = RegexValidator(r"^[A-Z]{3}$", "Use a three-letter ISO currency code.")


class OrderStatus(models.TextChoices):
    OPEN = "open"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class FulfillmentStatus(models.TextChoices):
    UNFULFILLED = "unfulfilled"
    FULFILLED = "fulfilled"


class MatchOutcome(models.TextChoices):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    POTENTIAL_DUPLICATE = "potential_duplicate"
    AMBIGUOUS = "ambiguous"
    DATA_INCONSISTENCY = "data_inconsistency"
    REQUIRES_MANUAL_REVIEW = "requires_manual_review"


class ExceptionKind(models.TextChoices):
    PAYMENT_UNMATCHED = "payment_unmatched"
    ORDER_UNPAID = "order_unpaid"
    PAYMENT_UNFULFILLED = "payment_unfulfilled"
    AMBIGUOUS = "ambiguous"
    DUPLICATE = "duplicate"
    AMOUNT_MISMATCH = "amount_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    MISSING_SOURCE = "missing_source"


class ExceptionStatus(models.TextChoices):
    OPEN = "open"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class InternalOrder(models.Model):
    """Merchant-owned operational order. There is no external fulfillment integration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="internal_orders")
    internal_reference = models.CharField(max_length=64)
    external_reference = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    status = models.CharField(max_length=16, choices=OrderStatus.choices, default=OrderStatus.OPEN)
    fulfillment_status = models.CharField(
        max_length=16, choices=FulfillmentStatus.choices, default=FulfillmentStatus.UNFULFILLED
    )
    customer_reference = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "internal_reference"], name="recon_order_ref_unique"),
        ]
        indexes = [
            models.Index(fields=["merchant", "external_reference"]),
            models.Index(fields=["merchant", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.internal_reference


class ReconciliationException(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="recon_exceptions")
    kind = models.CharField(max_length=32, choices=ExceptionKind.choices)
    outcome = models.CharField(max_length=32, choices=MatchOutcome.choices)
    status = models.CharField(max_length=16, choices=ExceptionStatus.choices, default=ExceptionStatus.OPEN)
    severity = models.CharField(max_length=16, default="attention")
    explanation = models.CharField(max_length=400)
    transaction = models.ForeignKey(PayPalTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    invoice = models.ForeignKey(PayPalInvoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    order = models.ForeignKey(InternalOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="exceptions")
    resolution_code = models.CharField(max_length=64, blank=True)
    resolution_note = models.CharField(max_length=400, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "status", "-created_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.kind}:{self.id}"


class ResolutionEvent(models.Model):
    """Append-only history of an exception decision. Does not alter PayPal records."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exception = models.ForeignKey(ReconciliationException, on_delete=models.CASCADE, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=16)
    note = models.CharField(max_length=400, blank=True)
    resolution_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Resolution events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Resolution events are append-only.")
