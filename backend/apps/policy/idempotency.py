"""Claim an idempotency key inside a transaction. Same key + same body is a replay."""

from __future__ import annotations

import hashlib
import json

from django.db import IntegrityError, transaction

from apps.core.exceptions import ApiError
from apps.merchants.models import Merchant
from apps.policy.models import IdempotencyKey


def fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def claim(
    *,
    merchant: Merchant,
    action: str,
    key: str,
    payload: dict,
    resource_type: str = "",
    resource_id: str = "",
) -> IdempotencyKey:
    """Insert the key, or raise already_executed / idempotency_conflict on replay."""
    key = (key or "").strip()
    if not key or len(key) > 128:
        raise ApiError("Provide an idempotency key of 1–128 characters.", code="validation_error", status_code=400)
    digest = fingerprint(payload)
    try:
        with transaction.atomic():
            return IdempotencyKey.objects.create(
                merchant=merchant,
                key=key,
                action=action,
                fingerprint=digest,
                resource_type=resource_type,
                resource_id=str(resource_id),
            )
    except IntegrityError:
        existing = IdempotencyKey.objects.filter(merchant=merchant, action=action, key=key).first()
        if existing and existing.fingerprint == digest:
            raise ApiError("This action has already been submitted.", code="already_executed", status_code=409)
        raise ApiError(
            "This idempotency key was already used with different details.",
            code="idempotency_conflict",
            status_code=409,
        )
