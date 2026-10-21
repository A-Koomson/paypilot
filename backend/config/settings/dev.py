"""Local development settings. Never use in production."""

from __future__ import annotations

from config.env import env, env_list

from .base import *  # noqa: F401,F403
from .base import EMAIL_HOST, FRONTEND_URL

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-do-not-use-in-production-0000")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]", "backend", "testserver"])
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [FRONTEND_URL, "http://127.0.0.1:5173"])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [FRONTEND_URL, "http://127.0.0.1:5173"])

# Emails are printed to the backend console unless SMTP is configured. The API reports
# `delivery_mode: "console"` so the UI never claims a real email was delivered.
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_DELIVERY_MODE = "smtp"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    EMAIL_DELIVERY_MODE = "console"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
API_DOCS_ENABLED = True
