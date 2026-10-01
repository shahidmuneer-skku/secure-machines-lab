from __future__ import annotations

from typing import Any

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml.apikeys.permissions import require_scope
from sml.core import audit
from sml.core.exceptions import ApiError
from sml.core.idempotency import idempotent
from sml.core.middleware import client_ip
from sml.core.models import PlatformSettings
from sml.core.pagination import DefaultCursorPagination
from sml.core.permissions import admin_permissions, require
from sml.core.throttling import JobCreateThrottle
from sml.credits import pricing
from sml.jobs.models import Job, JobTask
from sml.media.models import MediaObject

from . import services
from .registry import MODES, registry, server_status
from .serializers import (
    StudioAdminSerializer,
    StudioAdminUpdateSerializer,
    StudioConfigSerializer,
    StudioJobCreateSerializer,
    StudioJobSerializer,
)

TAG = ["studio"]


def studio_jobs(request: Request):  # type: ignore[no-untyped-def]
    return (Job.objects.filter(user=request.user, kind=Job.Kind.STUDIO, deleted_at__isnull=True)
            .prefetch_related(Prefetch("tasks", queryset=JobTask.objects.order_by("created_at")), "outputs"))


def _context(request: Request) -> dict[str, Any]:
    return {"request": request, "staff": services.can_choose_model(request.user)}


class StudioConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, responses=StudioConfigSerializer,
                   summary="What the image studio offers right now (controls per mode, prices)")
    def get(self, request: Request) -> Response:
        return Response(services.studio_config(request.user))


class StudioJobListCreateView(generics.ListAPIView):
    serializer_class = StudioJobSerializer
    pagination_class = DefaultCursorPagination
    queryset = Job.objects.none()

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [IsAuthenticated(), require_scope("studio:write")(), require("use_studio")()]
        return [IsAuthenticated(), require_scope("jobs:read")()]

    def get_throttles(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [JobCreateThrottle(), *super().get_throttles()]
        return super().get_throttles()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return studio_jobs(self.request)

    def get_serializer_context(self) -> dict[str, Any]:
        return _context(self.request)

    @extend_schema(tags=TAG, summary="My image studio history (newest first)")
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=TAG, request=StudioJobCreateSerializer, responses={202: StudioJobSerializer},
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
                   summary="Generate or edit images. Charged per delivered image; follow progress via SSE.")
    @idempotent()
    def post(self, request: Request) -> Response:
        ser = StudioJobCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ids = [str(i) for i in d["reference_ids"]]
        found = {str(m.pk): m for m in MediaObject.objects.filter(owner=request.user, pk__in=ids)}
        missing = [i for i in ids if i not in found]
        if missing:
            raise ApiError(f"Unknown media: {', '.join(missing)}", extra={"reference_ids": missing})
        req = services.StudioRequest(
            mode=d["mode"], prompt=d["prompt"], negative_prompt=d["negative_prompt"], aspect_ratio=d["aspect_ratio"],
            steps=d["steps"], guidance=d["guidance"], seed=d["seed"], count=d["count"], transparent=d["transparent"],
            references=[found[i] for i in dict.fromkeys(ids)], consent=d["consent"], model=d["model"],
            locale=getattr(request.user, "locale", "en"))
        api_key = getattr(request, "auth", None)
        source = "api" if hasattr(api_key, "prefix") else "web"
        consent_meta = {"ip": client_ip(request), "user_agent": request.headers.get("User-Agent", "")[:300]}
        job = services.create_studio_job(request.user, req, source=source, api_key=api_key, consent_meta=consent_meta)
        job = studio_jobs(request).get(pk=job.pk)
        return Response(StudioJobSerializer(job, context=_context(request)).data, status=status.HTTP_202_ACCEPTED)


class StudioJobDetailView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=TAG, responses=StudioJobSerializer, summary="One studio job with its images")
    def get(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(studio_jobs(request), pk=pk)
        return Response(StudioJobSerializer(job, context=_context(request)).data)


class StudioAdminView(APIView):
    """Admin → Studio: which model users get per mode, and the studio server's state."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        cap = "manage_models" if self.request.method == "PATCH" else "view_queues"
        return [p() for p in admin_permissions(cap)]

    @staticmethod
    def _payload() -> dict[str, Any]:
        cfg = PlatformSettings.load()
        reg = registry()
        status_ = server_status()
        installed = status_.get("models") or {}
        return {
            "enabled": cfg.studio_enabled, "generate_model": cfg.studio_generate_model,
            "edit_model": cfg.studio_edit_model,
            "prices": {mode: pricing.studio_unit_price(mode) for mode in MODES},
            "server": {k: v for k, v in status_.items() if k != "models"},
            "models": [{"id": m.id, "name": m.name, "vendor": m.vendor, "license": m.license,
                        "commercial": m.commercial, "modes": list(m.modes),
                        "installed": bool((installed.get(m.id) or {}).get("installed")),
                        "weights_gb": (installed.get(m.id) or {}).get("weights_gb"),
                        "loaded": m.id in (status_.get("loaded") or []),
                        "controls": {mode: m.controls(mode, reg.limits) for mode in m.modes}}
                       for m in reg.models.values()],
        }

    @extend_schema(tags=["admin"], responses=StudioAdminSerializer, summary="Image studio models and server")
    def get(self, request: Request) -> Response:
        return Response(self._payload())

    @extend_schema(tags=["admin"], request=StudioAdminUpdateSerializer, responses=StudioAdminSerializer,
                   summary="Choose the studio's model per mode (it stays loaded on the studio GPU)")
    def patch(self, request: Request) -> Response:
        ser = StudioAdminUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        cfg = PlatformSettings.load()
        before = {"enabled": cfg.studio_enabled, "generate_model": cfg.studio_generate_model,
                  "edit_model": cfg.studio_edit_model}
        for mode in MODES:
            key = f"{mode}_model"
            if key in d:
                model = registry().get(d[key]) if d[key] else None
                if d[key] and (model is None or not model.supports(mode)):
                    raise ApiError(f"{d[key]} cannot {mode} images.")
                setattr(cfg, f"studio_{key}", d[key])
        if "enabled" in d:
            cfg.studio_enabled = d["enabled"]
        cfg.save()
        services.sync_keep()
        after = {"enabled": cfg.studio_enabled, "generate_model": cfg.studio_generate_model,
                 "edit_model": cfg.studio_edit_model}
        audit.record("admin.studio_setup", request=request, target_type="core.platformsettings", target_id="1",
                     before=before, after=after)
        return Response(self._payload())
