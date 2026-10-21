from __future__ import annotations

import uuid

from django.db import models

from apps.merchants.models import Merchant


class IdempotencyKey(models.Model):
    """One-time claim for a merchant-scoped sensitive operation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="idempotency_keys")
    key = models.CharField(max_length=128)
    action = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=64, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "action", "key"], name="policy_idempotency_unique"),
        ]
        indexes = [models.Index(fields=["merchant", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action}:{self.key}"
