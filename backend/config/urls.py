from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core import health

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"

urlpatterns = [
    path("api/health/live/", health.live, name="health-live"),
    path("api/health/ready/", health.ready, name="health-ready"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.merchants.urls")),
    path("api/", include("apps.integrations.urls")),
    path("api/", include("apps.agent.urls")),
    path("api/", include("apps.recovery.urls")),
    path("api/", include("apps.reconciliation.urls")),
    path("api/", include("apps.audit.urls")),
]

if getattr(settings, "API_DOCS_ENABLED", False):
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]
