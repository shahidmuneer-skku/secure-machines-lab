"""HTTP endpoints for long-form streaming scans (see streams.py)."""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml.accounts.models import User
from sml.apikeys.permissions import require_scope
from sml.core.idempotency import idempotent
from sml.core.permissions import require
from sml.core.throttling import JobCreateThrottle
from sml.credits import pricing

from . import streams

TAG = ["long-video"]


class FaceCropSerializer(serializers.Serializer):
    support = serializers.ChoiceField(choices=["always", "optional", "none"])
    default = serializers.BooleanField()


class StreamModelSerializer(serializers.Serializer):
    model_id = serializers.CharField()
    name = serializers.CharField()
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    face_crop = FaceCropSerializer()


class StreamCatalogSerializer(serializers.Serializer):
    online = serializers.BooleanField()
    models = StreamModelSerializer(many=True)
    price_per_minute = serializers.IntegerField()
    max_bytes = serializers.IntegerField()
    max_seconds = serializers.IntegerField()


class StreamSessionRequestSerializer(serializers.Serializer):
    model_id = serializers.CharField(max_length=64)
    file_name = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1)
    duration_seconds = serializers.FloatField(min_value=0.1)
    start_seconds = serializers.FloatField(min_value=0, default=0.0)
    end_seconds = serializers.FloatField(required=False, allow_null=True, default=None)
    interval_seconds = serializers.FloatField(default=5.0)
    whole_video = serializers.BooleanField(default=False)
    face_crop = serializers.BooleanField(required=False, allow_null=True, default=None)
    locale = serializers.ChoiceField(choices=User.Locale.choices, required=False)


class StreamSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    ws_url = serializers.CharField()
    token = serializers.CharField()
    credits_reserved = serializers.IntegerField()
    reserved_seconds = serializers.FloatField()


class StreamModelsView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(tags=TAG, responses=StreamCatalogSerializer,
                   summary="Detectors available for long-form streaming, with the price per minute")
    def get(self, request: Request) -> Response:
        try:
            models, online = streams.available_models(), True
        except streams.StreamServiceUnavailable:
            models, online = [], False
        return Response({
            "online": online,
            "models": [{"model_id": m["model_id"], "name": m.get("name") or m["model_id"],
                        "available": bool(m.get("available")), "reason": m.get("reason") or "",
                        "face_crop": {"support": (m.get("face_crop") or {}).get("support", "none"),
                                      "default": bool((m.get("face_crop") or {}).get("default", False))}}
                       for m in models],
            "price_per_minute": pricing.price(pricing.Key.LONG_VIDEO_PER_MINUTE),
            "max_bytes": settings.UPLOAD_MAX_VIDEO_BYTES,
            "max_seconds": settings.UPLOAD_MAX_VIDEO_SECONDS,
        })


class StreamSessionCreateView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write"), require("run_long_video")]
    throttle_classes = [JobCreateThrottle]

    @extend_schema(tags=TAG, request=StreamSessionRequestSerializer, responses={201: StreamSessionSerializer},
                   summary="Pay for a long-form scan and get a token for the stream service")
    @idempotent(required=False)
    def post(self, request: Request) -> Response:
        ser = StreamSessionRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        req = streams.StreamRequest(
            model_id=d["model_id"], file_name=d["file_name"], file_size=d["file_size"],
            duration_seconds=d["duration_seconds"], start_seconds=d["start_seconds"], end_seconds=d["end_seconds"],
            interval_seconds=d["interval_seconds"], whole_video=d["whole_video"], face_crop=d["face_crop"],
            locale=d.get("locale") or getattr(request.user, "locale", "en"),
        )
        session, token = streams.create_session(request.user, req)
        return Response({"session_id": session.pk, "job_id": session.job_id, "ws_url": settings.STREAM_PUBLIC_URL,
                         "token": token, "credits_reserved": session.job.credits_quoted,
                         "reserved_seconds": session.reserved_seconds}, status=status.HTTP_201_CREATED)


class StreamEventView(APIView):
    """Internal: progress reports from the stream service. Authenticated by the shared key only."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def post(self, request: Request, pk: str) -> Response:
        if not streams.verify_service_key(request.headers.get("X-Stream-Key")):
            raise PermissionDenied("Invalid stream service key.")
        return Response(streams.handle_event(str(pk), request.data))
