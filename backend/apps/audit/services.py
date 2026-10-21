"""Audit service. The only supported way to write audit events."""

from __future__ import annotations

from typing import Any

from apps.audit.models import AuditEvent
from apps.core.context import request_id_var
from apps.core.logging import REDACTED, is_sensitive_key


def _sanitise(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): (REDACTED if is_sensitive_key(str(k)) else _sanitise(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitise(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def record(
    action: str,
    *,
    actor=None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=_sanitise(metadata or {}),
        request_id=request_id_var.get() if request_id_var.get() != "-" else "",
    )
