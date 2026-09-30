"""Self-service API key management (browser session only: keys cannot manage keys)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.core import audit
from sml.core.exceptions import ApiError
from sml.core.permissions import SessionOnly, require

from .models import ApiKey, Scope
from .serializers import (
    ApiKeyCreatedSerializer,
    ApiKeySerializer,
    ApiKeyUsageDailySerializer,
    ApiRequestLogSerializer,
)
from .services import MAX_KEYS_PER_USER, issue_key, revoke, rotate

PERMS = [SessionOnly, require("manage_own_api_keys")]


class TooManyKeys(ApiError):
    default_code = "API_KEY_LIMIT"
    default_detail = f"You can have at most {MAX_KEYS_PER_USER} active API keys. Revoke one first."
    title = "API key limit reached"


class ApiKeyListCreateView(APIView):
    permission_classes = PERMS

    @extend_schema(tags=["api-keys"], responses=ApiKeySerializer(many=True), summary="List my API keys")
    def get(self, request: Request) -> Response:
        keys = ApiKey.objects.filter(user=request.user)
        return Response(ApiKeySerializer(keys, many=True).data)

    @extend_schema(tags=["api-keys"], request=ApiKeySerializer, responses={201: ApiKeyCreatedSerializer},
                   summary="Create an API key (the secret is returned once)")
    def post(self, request: Request) -> Response:
        ser = ApiKeySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        active = ApiKey.objects.filter(user=request.user, revoked_at__isnull=True).count()
        if active >= MAX_KEYS_PER_USER:
            raise TooManyKeys()
        d = ser.validated_data
        issued = issue_key(
            request.user, name=d["name"], scopes=d["scopes"], allowed_ips=d.get("allowed_ips"),
            allowed_models=d.get("allowed_models"), rate_limit_per_minute=d.get("rate_limit_per_minute"),
            expires_at=d.get("expires_at"),
        )
        audit.record("api_key.created", request=request, target=issued.api_key,
                     after={"name": issued.api_key.name, "scopes": issued.api_key.scopes})
        data = ApiKeySerializer(issued.api_key).data | {"key": issued.plaintext}
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(APIView):
    permission_classes = PERMS

    def _get(self, request: Request, pk: str) -> ApiKey:
        return get_object_or_404(ApiKey, pk=pk, user=request.user)

    @extend_schema(tags=["api-keys"], responses=ApiKeySerializer, summary="Get an API key")
    def get(self, request: Request, pk: str) -> Response:
        return Response(ApiKeySerializer(self._get(request, pk)).data)

    @extend_schema(tags=["api-keys"], request=ApiKeySerializer, responses=ApiKeySerializer,
                   summary="Update name, scopes, IP allowlist, model allowlist, rate limit or expiry")
    def patch(self, request: Request, pk: str) -> Response:
        key = self._get(request, pk)
        if key.revoked_at:
            raise ApiError("Revoked keys cannot be edited.")
        before = ApiKeySerializer(key).data
        ser = ApiKeySerializer(key, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record("api_key.updated", request=request, target=key, before=dict(before), after=dict(ser.data))
        return Response(ser.data)

    @extend_schema(tags=["api-keys"], responses={204: None}, summary="Revoke an API key")
    def delete(self, request: Request, pk: str) -> Response:
        key = revoke(self._get(request, pk))
        audit.record("api_key.revoked", request=request, target=key)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApiKeyRotateView(APIView):
    permission_classes = PERMS

    @extend_schema(tags=["api-keys"], request=None, responses={201: ApiKeyCreatedSerializer},
                   summary="Rotate: issue a replacement key and revoke this one")
    def post(self, request: Request, pk: str) -> Response:
        key = get_object_or_404(ApiKey, pk=pk, user=request.user, revoked_at__isnull=True)
        issued = rotate(key)
        audit.record("api_key.rotated", request=request, target=issued.api_key, before={"old": str(key.pk)})
        data = ApiKeySerializer(issued.api_key).data | {"key": issued.plaintext}
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyUsageView(APIView):
    permission_classes = PERMS

    @extend_schema(tags=["api-keys"], responses=schemas.ApiKeyUsageResponseSerializer, summary="Daily usage and recent requests for a key")
    def get(self, request: Request, pk: str) -> Response:
        key = get_object_or_404(ApiKey, pk=pk, user=request.user)
        days = int(request.query_params.get("days", 30))
        since = timezone.localdate() - timedelta(days=min(max(days, 1), 365))
        daily = key.usage_days.filter(date__gte=since).order_by("date")
        totals = daily.aggregate(requests=Sum("requests"), errors=Sum("errors"),
                                 jobs_created=Sum("jobs_created"), credits_spent=Sum("credits_spent"))
        recent = key.request_logs.all()[:50]
        return Response({
            "totals": {k: v or 0 for k, v in totals.items()},
            "daily": ApiKeyUsageDailySerializer(daily, many=True).data,
            "recent_requests": ApiRequestLogSerializer(recent, many=True).data,
        })


class ScopeListView(APIView):
    permission_classes = PERMS

    @extend_schema(tags=["api-keys"], responses=schemas.IdLabelSerializer(many=True), summary="Available API key scopes")
    def get(self, request: Request) -> Response:
        return Response([{"id": s.value, "label": s.label} for s in Scope])
