"""Test settings: fast hashing, in-memory email, local-memory cache, deterministic config."""

from __future__ import annotations

from .dev import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_DELIVERY_MODE = "smtp"  # locmem stands in for a working provider in tests
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGGING_CONFIG = None
PAYPAL_CLIENT_ID = ""
PAYPAL_CLIENT_SECRET = ""
PAYPAL_ENVIRONMENT = "sandbox"
LLM_API_KEY = ""
LLM_MODEL = ""
GOOGLE_OAUTH_CLIENT_ID = ""
GOOGLE_OAUTH_CLIENT_SECRET = ""
