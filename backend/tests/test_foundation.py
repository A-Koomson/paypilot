"""Phase 00: health, error envelope, logging redaction, audit, production configuration."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.db import connection

from apps.audit import services as audit
from apps.audit.models import AuditEvent
from apps.core.logging import REDACTED, JsonFormatter, RedactingFilter, redact_text

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.django_db
class TestHealth:
    def test_live(self, client):
        res = client.get("/api/health/live/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_ready_checks_database_and_migrations(self, client):
        res = client.get("/api/health/ready/")
        assert res.status_code == 200
        assert res.json()["checks"] == {"database": "ok", "migrations": "ok"}

    def test_ready_reports_degraded_when_database_unavailable(self, client, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(connection, "cursor", boom)
        res = client.get("/api/health/ready/")
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "degraded"
        assert "db down" not in json.dumps(body)  # no internals leaked

    def test_request_id_header_present_and_upstream_id_honoured(self, client):
        res = client.get("/api/health/live/", headers={"X-Request-ID": "abcdef123456"})
        assert res["X-Request-ID"] == "abcdef123456"
        res = client.get("/api/health/live/", headers={"X-Request-ID": "bad id with spaces!"})
        assert res["X-Request-ID"] != "bad id with spaces!"


@pytest.mark.django_db
class TestErrorEnvelope:
    def test_unknown_route_uses_json_envelope_without_stack_traces(self, client):
        res = client.get("/api/does-not-exist/")
        assert res.status_code == 404
        err = res.json()["error"]
        assert err["code"] == "not_found"
        assert "Traceback" not in json.dumps(res.json())


class TestLoggingRedaction:
    @pytest.mark.parametrize(
        "raw",
        [
            "Authorization: Bearer A21AAFEpH4PsADK7qSS7pSRsgzfENtu",
            "client_secret=supersecretvalue",
            "password: hunter2hunter2",
            "api_key=sk-abcdef123456",
        ],
    )
    def test_secrets_are_scrubbed_from_text(self, raw):
        cleaned = redact_text(raw)
        assert REDACTED in cleaned
        for leaked in ("A21AAFEpH4Ps", "supersecretvalue", "hunter2hunter2", "sk-abcdef"):
            assert leaked not in cleaned

    def test_extra_fields_and_json_output_are_redacted(self):
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "login attempt token=%s", ("abc123xyz",), None)
        record.otp = "123456"
        record.password = "pw"
        record.safe = "visible"
        RedactingFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["otp"] == REDACTED and payload["password"] == REDACTED
        assert payload["safe"] == "visible"
        assert "abc123xyz" not in payload["msg"]


@pytest.mark.django_db
class TestAudit:
    def test_events_are_sanitised_and_append_only(self):
        event = audit.record("test.event", metadata={"password": "x", "nested": {"token": "y", "ok": 1}})
        assert event.metadata["password"] == REDACTED
        assert event.metadata["nested"] == {"token": REDACTED, "ok": 1}
        with pytest.raises(RuntimeError):
            event.save()
        with pytest.raises(RuntimeError):
            event.delete()
        assert AuditEvent.objects.count() == 1


def _run_prod(env_overrides: dict, code: str = "import config.settings.prod as s; print('OK')"):
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "CORS_", "CSRF_", "FRONTEND_", "EMAIL_"))
    }
    env["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"
    env["DATABASE_URL"] = "postgres://u:p@127.0.0.1:5432/x"
    env.update(env_overrides)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60
    )


GOOD_PROD = {
    "DJANGO_SECRET_KEY": "x" * 20 + "prod-secret-key-value-that-is-long-enough-1234567890",
    "DJANGO_ALLOWED_HOSTS": "api.example.com",
    "CORS_ALLOWED_ORIGINS": "https://app.example.com",
    "FRONTEND_URL": "https://app.example.com",
}


class TestProductionSettings:
    def test_valid_configuration_loads_and_is_hardened(self):
        code = (
            "import config.settings.prod as s;"
            "assert s.DEBUG is False;"
            "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE;"
            "assert s.SESSION_COOKIE_HTTPONLY;"
            "assert s.SECURE_SSL_REDIRECT and s.SECURE_HSTS_SECONDS > 0;"
            "assert s.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO','https');"
            "assert s.CORS_ALLOWED_ORIGINS == ['https://app.example.com'];"
            "assert s.EMAIL_DELIVERY_MODE == 'disabled';"
            "print('OK')"
        )
        res = _run_prod(GOOD_PROD, code)
        assert res.returncode == 0, res.stderr
        assert "OK" in res.stdout

    @pytest.mark.parametrize(
        ("override", "fragment"),
        [
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "wildcard"),
            ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
            ({"DJANGO_SECRET_KEY": "short"}, "DJANGO_SECRET_KEY"),
            ({"DJANGO_SECRET_KEY": "dev-only-insecure-key-do-not-use-in-production-0000"}, "DJANGO_SECRET_KEY"),
            ({"CORS_ALLOWED_ORIGINS": "*"}, "CORS_ALLOWED_ORIGINS"),
            ({"CORS_ALLOWED_ORIGINS": "http://app.example.com"}, "CORS_ALLOWED_ORIGINS"),
            ({"FRONTEND_URL": "http://app.example.com"}, "FRONTEND_URL"),
        ],
    )
    def test_unsafe_configuration_is_rejected(self, override, fragment):
        res = _run_prod({**GOOD_PROD, **override})
        assert res.returncode != 0
        assert fragment in res.stderr

    def test_django_deploy_check_has_no_warnings(self):
        res = _run_prod(
            GOOD_PROD,
            "import django; django.setup();"
            "from django.core.management import call_command;"
            "call_command('check', deploy=True, fail_level='WARNING'); print('OK')",
        )
        assert res.returncode == 0, res.stderr + res.stdout
