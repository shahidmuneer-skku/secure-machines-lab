"""Anonymous homepage trial: a few image detections per day, then a sign-up prompt."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.core.captcha import captcha_enabled, verify_captcha
from sml.core.exceptions import ApiError
from sml.core.middleware import client_ip
from sml.core.models import PlatformSettings
from sml.core.throttling import TrialThrottle
from sml.jobs.models import Job
from sml.jobs.serializers import JobDetailSerializer
from sml.media import services as media_services
from sml.media.views import serve_object

from .services import create_trial_job, remaining

SALT = "sml.trial.device"
COOKIE_AGE = 365 * 24 * 3600


def guest_token_from(request: HttpRequest) -> str | None:
    try:
        return request.get_signed_cookie(settings.TRIAL_COOKIE_NAME, salt=SALT, default=None)
    except signing.BadSignature:
        return None


def _ensure_token(request: HttpRequest) -> tuple[str, bool]:
    token = guest_token_from(request)
    return (token, False) if token else (secrets.token_hex(16), True)


def _set_cookie(resp: HttpResponse, token: str) -> None:
    resp.set_signed_cookie(settings.TRIAL_COOKIE_NAME, token, salt=SALT, max_age=COOKIE_AGE, httponly=True,
                           samesite="Lax", secure=settings.SESSION_COOKIE_SECURE)


class TrialBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []


class TrialStatusView(TrialBase):
    @extend_schema(tags=["trial"], responses=schemas.TrialStatusSerializer, summary="Remaining free trial detections today")
    def get(self, request: Request) -> Response:
        token, new = _ensure_token(request)
        cfg = PlatformSettings.load()
        resp = Response({
            "enabled": cfg.guest_trial_enabled, "remaining": remaining(token, client_ip(request)),
            "per_day": cfg.guest_trial_images_per_day, "captcha_required": captcha_enabled(),
            "captcha_site_key": settings.TURNSTILE_SITE_KEY,
        })
        if new:
            _set_cookie(resp, token)
        return resp


class TrialDetectView(TrialBase):
    parser_classes = [MultiPartParser]
    throttle_classes = [TrialThrottle]

    @extend_schema(tags=["trial"], summary="Analyze one image without an account",
                   responses={202: schemas.TrialDetectResponseSerializer},
                   request={"multipart/form-data": {"type": "object", "properties": {
                       "file": {"type": "string", "format": "binary"}, "captcha_token": {"type": "string"},
                       "locale": {"type": "string"}}}})
    def post(self, request: Request) -> Response:
        token, new = _ensure_token(request)
        ip = client_ip(request)
        if not verify_captcha(request.data.get("captcha_token"), ip):
            raise ApiError("Please complete the CAPTCHA.", extra={"code": "CAPTCHA_REQUIRED"})
        upload = request.FILES.get("file")
        if upload is None:
            raise ApiError("Send the image in a multipart field named 'file'.")
        if remaining(token, ip) <= 0:
            from sml.core.exceptions import TrialExhausted

            raise TrialExhausted()
        media = media_services.ingest_file(upload, original_name=upload.name, guest_token=token)
        locale = request.data.get("locale") or "en"
        job = create_trial_job(media, device=token, ip=ip, locale=locale if locale in ("en", "ko", "de") else "en")
        resp = Response({"job_id": str(job.pk), "remaining": remaining(token, ip)}, status=status.HTTP_202_ACCEPTED)
        if new:
            _set_cookie(resp, token)
        return resp


class TrialJobView(TrialBase):
    @extend_schema(tags=["trial"], responses=JobDetailSerializer, summary="Trial job status and result")
    def get(self, request: Request, pk: str) -> Response:
        token = guest_token_from(request)
        job = get_object_or_404(Job.objects.select_related("media"), pk=pk, guest_token=token or "-",
                                source=Job.Source.TRIAL)
        data = JobDetailSerializer(job, context={
            "request": request, "media_url_prefix": "/api/v1/trial/media", "job_url_prefix": "/api/v1/trial/jobs",
            "lang": job.locale}).data
        data.pop("options", None)
        return Response(data)


class TrialMediaThumbnailView(TrialBase):
    @extend_schema(tags=["trial"], responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    def get(self, request: Request, pk: str) -> HttpResponse:
        from sml.media.models import MediaObject

        token = guest_token_from(request)
        media = get_object_or_404(MediaObject, pk=pk, guest_token=token or "-")
        return serve_object(media.thumbnail_key, content_type="image/jpeg", filename=f"{media.pk}.jpg")


class TrialArtifactView(TrialBase):
    @extend_schema(tags=["trial"], responses={(200, "image/png"): OpenApiTypes.BINARY})
    def get(self, request: Request, pk: str, artifact_id: str) -> HttpResponse:
        from sml.jobs.models import Artifact

        token = guest_token_from(request)
        art = get_object_or_404(Artifact, pk=artifact_id, job_id=pk, job__guest_token=token or "-")
        return serve_object(art.storage_key, content_type=art.content_type, filename=art.storage_key.rsplit("/")[-1])
