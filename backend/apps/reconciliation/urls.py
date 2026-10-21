from django.urls import path

from apps.reconciliation import views

urlpatterns = [
    path("reconciliation/orders/", views.OrderListView.as_view(), name="recon-orders"),
    path("reconciliation/run/", views.ReconciliationRunView.as_view(), name="recon-run"),
    path("reconciliation/exceptions/", views.ExceptionListView.as_view(), name="recon-exceptions"),
    path("reconciliation/exceptions/<uuid:pk>/", views.ExceptionDetailView.as_view(), name="recon-exception"),
    path("reconciliation/exceptions/<uuid:pk>/resolve/", views.ExceptionResolveView.as_view(), name="recon-resolve"),
    path("reconciliation/exceptions/<uuid:pk>/reopen/", views.ExceptionReopenView.as_view(), name="recon-reopen"),
]
