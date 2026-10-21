from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ApiError
from apps.core.permissions import IsMerchant, get_merchant
from apps.reconciliation import services
from apps.reconciliation.models import InternalOrder
from apps.reconciliation.services import serialize_exception, serialize_order


class OrderListView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: dict}, tags=["reconciliation"])
    def get(self, request):
        merchant = get_merchant(request)
        rows = InternalOrder.objects.filter(merchant=merchant)
        return Response({"results": [serialize_order(row) for row in rows]})

    @extend_schema(request=dict, responses={201: dict}, tags=["reconciliation"])
    def post(self, request):
        order = services.create_order(get_merchant(request), actor=request.user, data=request.data)
        return Response(serialize_order(order), status=201)


class ReconciliationRunView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=None, responses={200: dict}, tags=["reconciliation"])
    def post(self, request):
        return Response(services.run_matching(get_merchant(request), actor=request.user))


class ExceptionListView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(operation_id="reconciliation_exceptions_list", responses={200: dict}, tags=["reconciliation"])
    def get(self, request):
        items = services.list_exceptions(
            get_merchant(request),
            status=request.query_params.get("status") or "",
            kind=request.query_params.get("kind") or "",
        )
        return Response({"results": items})


class ExceptionDetailView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(operation_id="reconciliation_exceptions_retrieve", responses={200: dict}, tags=["reconciliation"])
    def get(self, request, pk):
        merchant = get_merchant(request)
        row = (
            merchant.recon_exceptions.select_related("transaction", "invoice", "order")
            .prefetch_related("history")
            .filter(pk=pk)
            .first()
        )
        if row is None:
            raise ApiError("Exception not found.", code="not_found", status_code=404)
        return Response(serialize_exception(row))


class ExceptionResolveView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["reconciliation"])
    def post(self, request, pk):
        row = services.resolve_exception(
            get_merchant(request),
            pk,
            actor=request.user,
            code=str(request.data.get("resolution_code") or ""),
            note=str(request.data.get("note") or ""),
        )
        return Response(serialize_exception(row))


class ExceptionReopenView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["reconciliation"])
    def post(self, request, pk):
        row = services.reopen_exception(
            get_merchant(request),
            pk,
            actor=request.user,
            note=str(request.data.get("note") or ""),
        )
        return Response(serialize_exception(row))
