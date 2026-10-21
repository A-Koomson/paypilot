from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models

from apps.merchants.models import Merchant

CURRENCY = RegexValidator(r"^[A-Z]{3}$", "Use a three-letter ISO currency code.")


class PayPalConnection(models.Model):
    """Per-merchant record of what has actually been verified against PayPal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name="paypal_connection")
    environment = models.CharField(max_length=16, default="sandbox")
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_message = models.CharField(max_length=240, blank=True)
    transactions_imported = models.PositiveIntegerField(default=0)
    invoices_imported = models.PositiveIntegerField(default=0)
    # Which of the verified endpoints succeeded on the last attempt.
    capabilities = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"PayPalConnection({self.merchant_id})"

    def state(self, *, configured: bool) -> str:
        if not configured:
            return "not_configured"
        if self.last_error_code and not self.last_verified_at:
            return "error"
        if not self.last_verified_at:
            return "not_connected"
        caps = self.capabilities or {}
        if caps.get("transactions") is False or caps.get("invoices") is False:
            return "limited"
        return "connected"


class PayPalTransaction(models.Model):
    """A transaction imported from Transaction Search. Amounts are never converted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="paypal_transactions")
    source_id = models.CharField(max_length=64)
    status = models.CharField(max_length=8)  # PayPal transaction_status code (S, P, D, V, …)
    event_code = models.CharField(max_length=16, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    initiated_at = models.DateTimeField(null=True, blank=True)
    updated_at_source = models.DateTimeField(null=True, blank=True)
    payer_email = models.EmailField(blank=True)
    note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["merchant", "source_id"], name="integrations_txn_source_unique")]
        indexes = [
            models.Index(fields=["merchant", "-initiated_at"]),
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["merchant", "currency"]),
        ]
        ordering = ["-initiated_at", "-created_at"]

    def __str__(self) -> str:
        return self.source_id


class PayPalInvoice(models.Model):
    """An invoice imported from Invoicing v2. Status is PayPal's own status string."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="paypal_invoices")
    source_id = models.CharField(max_length=64)
    invoice_number = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    due_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    recipient_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["merchant", "source_id"], name="integrations_inv_source_unique")]
        indexes = [models.Index(fields=["merchant", "-invoice_date"]), models.Index(fields=["merchant", "status"])]
        ordering = ["-invoice_date", "-created_at"]

    def __str__(self) -> str:
        return self.source_id
