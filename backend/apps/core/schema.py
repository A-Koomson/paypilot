"""OpenAPI extras so spectacular documents our cookie session authenticator."""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BrowserSessionScheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.BrowserSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": settings.SESSION_COOKIE_NAME}
