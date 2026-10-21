from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ApiError
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsMerchant, get_merchant
from apps.integrations import services
from apps.integrations.exceptions import PayPalError
from apps.integrations.models import PayPalInvoice, PayPalTransaction
from apps.integrations.serializers import InvoiceSerializer, TransactionSerializer


def _paypal_error(exc: PayPalError):
    raise ApiError(exc.public_message, code=exc.code, status_code=exc.status_code, details=exc.details)


class PayPalStatusView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: dict}, tags=["paypal"])
    def get(self, request):
        merchant = get_merchant(request)
        summary = services.connection_summary(merchant)
        return Response(
            {
                **summary,
                "supported_record_types": [
                    {
                        "type": "transactions",
                        "endpoint": "GET /v1/reporting/transactions",
                        "available": (summary.get("capabilities") or {}).get("transactions"),
                    },
                    {
                        "type": "invoices",
                        "endpoint": "GET /v2/invoicing/invoices",
                        "available": (summary.get("capabilities") or {}).get("invoices"),
                    },
                ],
                "unsupported_record_types": [
                    {
                        "type": "orders",
                        "reason": "The Orders v2 API creates and captures checkout orders; it does not list a merchant’s historical sales activity.",
                    }
                ],
            }
        )


class PayPalVerifyView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "sync"

    @extend_schema(request=None, responses={200: dict}, tags=["paypal"])
    def post(self, request):
        try:
            services.verify_credentials(get_merchant(request))
        except PayPalError as exc:
            _paypal_error(exc)
        return Response(services.connection_summary(get_merchant(request)))


class PayPalSyncView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "sync"

    @extend_schema(request=None, responses={200: dict}, tags=["paypal"])
    def post(self, request):
        try:
            result = services.synchronise(get_merchant(request))
        except PayPalError as exc:
            _paypal_error(exc)
        return Response(result)


class TransactionListView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: TransactionSerializer(many=True)}, tags=["paypal"])
    def get(self, request):
        merchant = get_merchant(request)
        qs = PayPalTransaction.objects.filter(merchant=merchant)
        status_filter = request.query_params.get("status")
        currency = request.query_params.get("currency")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if currency:
            qs = qs.filter(currency=currency.upper())
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TransactionSerializer(page, many=True).data)


class TransactionDetailView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: TransactionSerializer}, tags=["paypal"])
    def get(self, request, pk):
        merchant = get_merchant(request)
        record = PayPalTransaction.objects.filter(merchant=merchant, pk=pk).first()
        if record is None:
            raise ApiError("Transaction not found.", code="not_found", status_code=404)
        return Response(TransactionSerializer(record).data)


class InvoiceListView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: InvoiceSerializer(many=True)}, tags=["paypal"])
    def get(self, request):
        merchant = get_merchant(request)
        qs = PayPalInvoice.objects.filter(merchant=merchant)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(InvoiceSerializer(page, many=True).data)


class InvoiceDetailView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: InvoiceSerializer}, tags=["paypal"])
    def get(self, request, pk):
        merchant = get_merchant(request)
        record = PayPalInvoice.objects.filter(merchant=merchant, pk=pk).first()
        if record is None:
            raise ApiError("Invoice not found.", code="not_found", status_code=404)
        return Response(InvoiceSerializer(record).data)
