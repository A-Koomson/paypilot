from django.urls import path

from apps.merchants import views as v

urlpatterns = [
    path("merchant/profile/", v.MerchantProfileView.as_view(), name="merchant-profile"),
]
