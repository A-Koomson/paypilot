"""Settings shared by every environment. Environment-specific files override these."""

from __future__ import annotations

from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from config.env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

# Developer convenience only. Variables already present in the process environment win.
load_dotenv(REPO_ROOT / ".env", override=False)

# --- Core ------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "")  # dev.py supplies a dev-only default; prod.py validates it.
DEBUG = False
ALLOWED_HOSTS: list[str] = env_list("DJANGO_ALLOWED_HOSTS")
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APP_VERSION = env("APP_VERSION", "0.1.0")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.merchants",
    "apps.integrations",
    "apps.agent",
    "apps.audit",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.SessionLifetimeMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# --- Database ----------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgres://paypilot:paypilot@localhost:5432/paypilot",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}

# Database-backed cache so throttles and lockouts are shared across gunicorn workers.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "paypilot_cache",
    }
}

# --- Auth & sessions -----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "paypilot_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Sliding idle timeout (refreshed on each request) plus an absolute lifetime cap.
SESSION_IDLE_SECONDS = env_int("SESSION_IDLE_SECONDS", 2 * 60 * 60)
SESSION_ABSOLUTE_SECONDS = env_int("SESSION_ABSOLUTE_SECONDS", 24 * 60 * 60)
SESSION_COOKIE_AGE = SESSION_IDLE_SECONDS
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "paypilot_csrf"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True  # The SPA obtains its token from GET /api/auth/csrf/, not from the cookie.
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Email ownership + OTP policy
OTP_TTL_SECONDS = env_int("OTP_TTL_SECONDS", 10 * 60)
OTP_MAX_ATTEMPTS = env_int("OTP_MAX_ATTEMPTS", 5)
OTP_MAX_ISSUES_PER_HOUR = env_int("OTP_MAX_ISSUES_PER_HOUR", 6)
EMAIL_VERIFICATION_MAX_AGE_SECONDS = env_int("EMAIL_VERIFICATION_MAX_AGE_SECONDS", 3 * 24 * 60 * 60)
PASSWORD_RESET_TIMEOUT = env_int("PASSWORD_RESET_TIMEOUT", 60 * 60)
LOGIN_MAX_FAILED_ATTEMPTS = env_int("LOGIN_MAX_FAILED_ATTEMPTS", 8)
LOGIN_LOCKOUT_SECONDS = env_int("LOGIN_LOCKOUT_SECONDS", 15 * 60)

# Google OAuth (optional). Disabled automatically when credentials are absent.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = env("GOOGLE_OAUTH_REDIRECT_URI", "")

# --- Email -----------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "PayPilot <no-reply@localhost>")

# --- PayPal (server-side only) ---------------------------------------------------
PAYPAL_CLIENT_ID = env("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", "")
PAYPAL_ENVIRONMENT = (env("PAYPAL_ENVIRONMENT", "sandbox") or "sandbox").lower()
PAYPAL_HTTP_TIMEOUT_SECONDS = env_int("PAYPAL_HTTP_TIMEOUT_SECONDS", 15)
PAYPAL_MAX_RETRIES = env_int("PAYPAL_MAX_RETRIES", 3)
PAYPAL_SYNC_LOOKBACK_DAYS = env_int("PAYPAL_SYNC_LOOKBACK_DAYS", 90)

# --- AI provider (server-side only) ----------------------------------------------
LLM_PROVIDER = env("LLM_PROVIDER", "openai_compatible")
LLM_BASE_URL = env("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
LLM_MODEL = env("LLM_MODEL", "")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_TIMEOUT_SECONDS = env_int("LLM_TIMEOUT_SECONDS", 30)
AGENT_MAX_TOOL_CALLS = env_int("AGENT_MAX_TOOL_CALLS", 4)
AGENT_MAX_MESSAGE_CHARS = env_int("AGENT_MAX_MESSAGE_CHARS", 1000)
AGENT_CONVERSATION_RETENTION_DAYS = env_int("AGENT_CONVERSATION_RETENTION_DAYS", 30)

# --- DRF / OpenAPI ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.authentication.BrowserSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
        "otp": "10/hour",
        "password_reset": "5/hour",
        "sync": "10/hour",
        "assistant": "30/hour",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "PayPilot API",
    "DESCRIPTION": (
        "PayPilot is an independent product and is not affiliated with or endorsed by PayPal. "
        "Session-cookie authentication; send the token from GET /api/auth/csrf/ in X-CSRFToken "
        "on unsafe requests."
    ),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Static files ------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- i18n ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- CORS -------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# --- Logging ------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "apps.core.logging.RedactingFilter"}},
    "formatters": {"json": {"()": "apps.core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json", "filters": ["redact"]}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
