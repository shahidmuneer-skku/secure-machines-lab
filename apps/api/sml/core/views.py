"""Liveness / readiness probes."""

from __future__ import annotations

import logging

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthzView(APIView):
    """Process is up. Never touches dependencies."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadyzView(APIView):
    """Dependencies reachable: PostgreSQL, Redis, RabbitMQ."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        checks: dict[str, str] = {}
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001 - a readiness probe reports failures, never raises
            checks["database"] = "error"
        try:
            redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()
            checks["redis"] = "ok"
        except Exception:  # noqa: BLE001 - a readiness probe reports failures, never raises
            checks["redis"] = "error"
        try:
            from sml.celery import app

            with app.connection_for_write() as conn:
                conn.ensure_connection(max_retries=1, timeout=2)
            checks["broker"] = "ok"
        except Exception:  # noqa: BLE001 - a readiness probe reports failures, never raises
            checks["broker"] = "error"
        healthy = all(v == "ok" for v in checks.values())
        return Response({"status": "ok" if healthy else "degraded", "checks": checks}, status=200 if healthy else 503)
