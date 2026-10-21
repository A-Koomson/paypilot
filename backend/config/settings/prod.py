"""Production settings. Fails fast on unsafe or missing configuration."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from config.env import env, env_bool, env_int

from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    EMAIL_HOST,
    FRONTEND_URL,
    SECRET_KEY,
)

DEBUG = False

# Render always injects this. Accept it without requiring a duplicate DJANGO_ALLOWED_HOSTS entry.
_render_host = env("RENDER_EXTERNAL_HOSTNAME", "")
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)
if not CORS_ALLOWED_ORIGINS and FRONTEND_URL.startswith("https://"):
    CORS_ALLOWED_ORIGINS = [FRONTEND_URL]

# --- Fail fast on unsafe configuration -------------------------------------------------
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list explicit hosts (no wildcard).")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a unique random value of 50+ characters.")
if not CORS_ALLOWED_ORIGINS or any(o == "*" or not o.startswith("https://") for o in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be explicit https:// origins in production.")
if not FRONTEND_URL.startswith("https://"):
    raise ImproperlyConfigured("FRONTEND_URL must be an https:// URL in production.")
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# --- Transport security ------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_REDIRECT_EXEMPT = [r"^api/health/"]
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
# Deliberately off: the API is served from a shared platform domain (e.g. *.onrender.com), where
# applying HSTS to sibling subdomains or preloading is neither appropriate nor within our control.
# These two checks are silenced explicitly; every other `check --deploy` warning stays fatal in tests.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = env("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE

# --- Email: never pretend delivery happened ---------------------------------------------------
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_DELIVERY_MODE = "smtp"
else:
    EMAIL_BACKEND = "apps.core.email.DisabledEmailBackend"
    EMAIL_DELIVERY_MODE = "disabled"

API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", False)
