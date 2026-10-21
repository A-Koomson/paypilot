"""Session authentication that always checks CSRF, including unauthenticated POSTs.

DRF's built-in SessionAuthentication skips CSRF when there is no logged-in user, which
would leave login, registration and password-reset endpoints open to cross-site POSTs.
"""

from rest_framework.authentication import SessionAuthentication


class BrowserSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        self.enforce_csrf(request)
        user = getattr(request._request, "user", None)
        if not user or not user.is_active:
            return None
        return (user, None)
