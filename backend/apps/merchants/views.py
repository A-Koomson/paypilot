from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.core.permissions import IsMerchant, get_merchant
from apps.merchants.serializers import MerchantSerializer


class MerchantProfileView(APIView):
    """The signed-in merchant's own profile. There is deliberately no `/merchants/<id>/` route."""

    permission_classes = [IsMerchant]

    @extend_schema(responses={200: MerchantSerializer}, tags=["merchant"])
    def get(self, request):
        return Response(MerchantSerializer(get_merchant(request)).data)

    @extend_schema(request=MerchantSerializer, responses={200: MerchantSerializer}, tags=["merchant"])
    def patch(self, request):
        merchant = get_merchant(request)
        ser = MerchantSerializer(merchant, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record(
            "merchant.profile_updated",
            actor=request.user,
            target_type="merchant",
            target_id=merchant.id,
            metadata={"fields": sorted(request.data.keys())},
        )
        return Response(ser.data)
