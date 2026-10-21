from django.urls import path

from apps.audit.views import MerchantAuditView

urlpatterns = [
    path("audit/", MerchantAuditView.as_view(), name="merchant-audit"),
]
