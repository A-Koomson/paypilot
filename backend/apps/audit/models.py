from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.merchants.models import Merchant


class AuditEvent(models.Model):
    """Append-only record of security- and policy-relevant events.

    `metadata` is sanitised by `apps.audit.services.record` and must never hold secrets.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    merchant = models.ForeignKey(Merchant, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["merchant", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M:%S}" if self.created_at else self.action

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events are append-only.")
