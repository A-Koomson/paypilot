"""Health endpoints for load balancers and platform health checks."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger("paypilot.health")


@extend_schema(responses={200: OpenApiTypes.OBJECT}, tags=["health"], auth=[])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def live(request):
    """Liveness: the process is serving requests. Does not touch dependencies."""
    return Response({"status": "ok", "version": settings.APP_VERSION})


@extend_schema(responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT}, tags=["health"], auth=[])
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def ready(request):
    """Readiness: the database is reachable and all migrations are applied."""
    checks: dict[str, str] = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        checks["migrations"] = "ok" if not pending else "pending"
    except Exception:  # noqa: BLE001 - report failure without leaking internals
        logger.exception("readiness_check_failed")
        checks["database"] = "unavailable"
        checks.setdefault("migrations", "unknown")

    healthy = all(v == "ok" for v in checks.values())
    return Response(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
