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
from sml.core.exceptions import ApiError
from sml.core.idempotency import idempotent
from sml.core.permissions import require
from sml.core.throttling import JobCreateThrottle
from sml.credits import pricing

from . import streams

TAG = ["long-video"]


class StreamConfigSerializer(serializers.Serializer):
    online = serializers.BooleanField(help_text="The long-form service is reachable.")
    available = serializers.BooleanField(help_text="Long-form scans can be started right now.")
    price_per_minute = serializers.IntegerField()
    max_bytes = serializers.IntegerField()
    max_seconds = serializers.IntegerField()


class StreamSessionRequestSerializer(serializers.Serializer):
    """The detector is the administrator's choice; the caller only picks the range and mode."""

    file_name = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1)
    duration_seconds = serializers.FloatField(min_value=0.1)
    start_seconds = serializers.FloatField(min_value=0, default=0.0)
    end_seconds = serializers.FloatField(required=False, allow_null=True, default=None)
    interval_seconds = serializers.FloatField(default=5.0)
    whole_video = serializers.BooleanField(default=False)
    locale = serializers.ChoiceField(choices=User.Locale.choices, required=False)


class StreamSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    ws_url = serializers.CharField()
    token = serializers.CharField()
    credits_reserved = serializers.IntegerField()
    reserved_seconds = serializers.FloatField()


class StreamConfigView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(tags=TAG, responses=StreamConfigSerializer,
                   summary="Whether long-form scans are available, the price per minute and the size limits")
    def get(self, request: Request) -> Response:
        try:
            streams.configured_model()
            online = available = True
        except streams.StreamServiceUnavailable:
            online = available = False
        except ApiError:
            online, available = True, False
        return Response({
            "online": online, "available": available,
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
            file_name=d["file_name"], file_size=d["file_size"],
            duration_seconds=d["duration_seconds"], start_seconds=d["start_seconds"], end_seconds=d["end_seconds"],
            interval_seconds=d["interval_seconds"], whole_video=d["whole_video"],
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


class StreamClaimView(APIView):
    """Internal: the stream service fetches what a session paid for (once), keyed by the token's sid."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes: list = []

    @extend_schema(exclude=True)
    def post(self, request: Request, pk: str) -> Response:
        if not streams.verify_service_key(request.headers.get("X-Stream-Key")):
            raise PermissionDenied("Invalid stream service key.")
        return Response(streams.claim_session(str(pk)))
