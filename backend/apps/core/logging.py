"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from apps.core.context import request_id_var

REDACTED = "[REDACTED]"

# Keys whose values must never reach logs, whatever the logger or call site.
SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "otp",
    "passcode",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "session",
    "csrf",
    "credential",
)

_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-~+/]+=*"), r"\1" + REDACTED),
    (
        re.compile(r"(?i)((?:client_)?secret|password|access_token|api[_-]?key|token)(\s*[=:]\s*)[^\s,;&\"']+"),
        r"\1\2" + REDACTED,
    ),
    (re.compile(r"(?i)(basic\s+)[A-Za-z0-9+/=]{8,}"), r"\1" + REDACTED),
]

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if is_sensitive_key(str(k)) else redact_value(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class RedactingFilter(logging.Filter):
    """Scrubs the message and any `extra` fields before a record is formatted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging raise
            message = str(record.msg)
        record.msg = redact_text(message)
        record.args = ()
        for key in list(record.__dict__):
            if key in _STANDARD_ATTRS:
                continue
            record.__dict__[key] = REDACTED if is_sensitive_key(key) else redact_value(record.__dict__[key])
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)
