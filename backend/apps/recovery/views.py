from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ApiError
from apps.core.permissions import IsMerchant, get_merchant
from apps.recovery import services
from apps.recovery.services import serialize_action, serialize_case


class RecoveryQueueView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: dict}, tags=["recovery"])
    def get(self, request):
        merchant = get_merchant(request)
        items = services.list_queue(
            merchant,
            status=request.query_params.get("status") or "",
            currency=request.query_params.get("currency") or "",
            customer=request.query_params.get("customer") or "",
            sort=request.query_params.get("sort") or "priority",
        )
        return Response({"results": items, "metrics": services.metrics(merchant)})


class RecoveryCaseDetailView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: dict}, tags=["recovery"])
    def get(self, request, pk):
        merchant = get_merchant(request)
        services.refresh_cases(merchant)
        case = merchant.recovery_cases.select_related("invoice").filter(pk=pk).first()
        if case is None:
            raise ApiError("Recovery case not found.", code="not_found", status_code=404)
        return Response(serialize_case(case))


class RecoveryPriorityView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        try:
            priority = int(request.data.get("priority"))
        except (TypeError, ValueError):
            raise ApiError("Priority must be an integer.", code="validation_error", status_code=400)
        case = services.set_priority(get_merchant(request), pk, actor=request.user, priority=priority)
        return Response(serialize_case(case))


class RecoveryDraftView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        action = services.prepare_draft(
            get_merchant(request),
            pk,
            actor=request.user,
            subject=str(request.data.get("subject") or ""),
            body=str(request.data.get("body") or ""),
        )
        return Response(serialize_action(action))


class RecoverySubmitView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        action = services.submit_for_approval(
            get_merchant(request),
            pk,
            actor=request.user,
            delivery=str(request.data.get("delivery") or ""),
        )
        return Response(serialize_action(action))


class RecoveryApproveView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=dict, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        action = services.approve_action(
            get_merchant(request),
            pk,
            actor=request.user,
            confirm=request.data.get("confirm") is True,
        )
        return Response(serialize_action(action))


class RecoveryRejectView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(request=None, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        action = services.reject_action(get_merchant(request), pk, actor=request.user)
        return Response(serialize_action(action))


class RecoveryExecuteView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "sync"

    @extend_schema(request=dict, responses={200: dict}, tags=["recovery"])
    def post(self, request, pk):
        action = services.execute_action(
            get_merchant(request),
            pk,
            actor=request.user,
            confirm=request.data.get("confirm") is True,
            idempotency_key=str(request.data.get("idempotency_key") or request.headers.get("Idempotency-Key") or ""),
        )
        return Response(serialize_action(action))
