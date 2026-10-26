"""Email delivery: Resend HTTPS succeeds or fails honestly. SMTP-on-Render is not assumed."""

from __future__ import annotations

import requests

from apps.core.email import send_email


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_resend_http_success_is_delivered(settings, monkeypatch):
    settings.EMAIL_DELIVERY_MODE = "smtp"
    settings.RESEND_API_KEY = "re_test"
    settings.DEFAULT_FROM_EMAIL = "PayPilot <onboarding@resend.dev>"

    def fake_post(url, **kwargs):
        assert url == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == "Bearer re_test"
        assert kwargs["json"]["to"] == ["ada@example.com"]
        return _Response(200, {"id": "msg_1"})

    monkeypatch.setattr("apps.core.email.requests.post", fake_post)
    result = send_email(to="ada@example.com", subject="Confirm", body="Link")
    assert result.delivered is True
    assert result.mode == "smtp"


def test_resend_http_rejection_is_not_delivered(settings, monkeypatch):
    settings.EMAIL_DELIVERY_MODE = "smtp"
    settings.RESEND_API_KEY = "re_test"
    settings.DEFAULT_FROM_EMAIL = "PayPilot <onboarding@resend.dev>"

    def fake_post(url, **kwargs):
        return _Response(422, {"message": "invalid"})

    monkeypatch.setattr("apps.core.email.requests.post", fake_post)
    result = send_email(to="ada@example.com", subject="Confirm", body="Link")
    assert result.delivered is False
    assert result.mode == "smtp"


def test_resend_transport_error_is_not_delivered(settings, monkeypatch):
    settings.EMAIL_DELIVERY_MODE = "smtp"
    settings.RESEND_API_KEY = "re_test"

    def fake_post(url, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr("apps.core.email.requests.post", fake_post)
    result = send_email(to="ada@example.com", subject="Confirm", body="Link")
    assert result.delivered is False
