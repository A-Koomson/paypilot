from django.urls import path

from apps.integrations import views as v

urlpatterns = [
    path("integrations/paypal/", v.PayPalStatusView.as_view(), name="paypal-status"),
    path("integrations/paypal/verify/", v.PayPalVerifyView.as_view(), name="paypal-verify"),
    path("integrations/paypal/sync/", v.PayPalSyncView.as_view(), name="paypal-sync"),
    path("integrations/paypal/transactions/", v.TransactionListView.as_view(), name="paypal-transactions"),
    path("integrations/paypal/transactions/<uuid:pk>/", v.TransactionDetailView.as_view(), name="paypal-transaction"),
    path("integrations/paypal/invoices/", v.InvoiceListView.as_view(), name="paypal-invoices"),
    path("integrations/paypal/invoices/<uuid:pk>/", v.InvoiceDetailView.as_view(), name="paypal-invoice"),
]
