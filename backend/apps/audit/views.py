from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.core.pagination import StandardPagination
from apps.core.permissions import IsMerchant, get_merchant


class MerchantAuditView(APIView):
    permission_classes = [IsMerchant]

    @extend_schema(responses={200: dict}, tags=["audit"])
    def get(self, request):
        merchant = get_merchant(request)
        qs = AuditEvent.objects.filter(merchant=merchant).select_related("actor")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [
            {
                "id": str(event.id),
                "action": event.action,
                "actor_email": event.actor.email if event.actor else None,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "metadata": event.metadata,
                "created_at": event.created_at,
            }
            for event in page
        ]
        return paginator.get_paginated_response(data)
