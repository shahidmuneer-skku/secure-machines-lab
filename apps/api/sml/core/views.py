"""Liveness / readiness probes."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import CORE_CHECKS, run_checks


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
        checks = {name: r["status"] for name, r in run_checks(CORE_CHECKS).items()}
        healthy = all(v == "ok" for v in checks.values())
        return Response({"status": "ok" if healthy else "degraded", "checks": checks}, status=200 if healthy else 503)
