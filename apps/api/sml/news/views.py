from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.apikeys.permissions import require_scope
from sml.core.exceptions import ApiError
from sml.core.idempotency import idempotent
from sml.core.permissions import require
from sml.jobs.models import Job
from sml.jobs.serializers import JobDetailSerializer, JobListSerializer
from sml.jobs.views import user_jobs
from sml.media.models import MediaObject

from .services import create_news_job


class NewsCaseSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    violence_level = serializers.CharField(max_length=50, required=False, allow_blank=True)
    description = serializers.CharField(max_length=10_000, required=False, allow_blank=True)
    social_media_link = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=10)
    locale = serializers.ChoiceField(choices=["en", "ko", "de"], required=False)


class NewsCaseListCreateView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [IsAuthenticated(), require_scope("news:write")(), require("run_news_verification")()]
        return [IsAuthenticated(), require_scope("jobs:read")()]

    @extend_schema(tags=["news"], responses=JobListSerializer(many=True), summary="My news verification cases")
    def get(self, request: Request) -> Response:
        jobs = user_jobs(request).filter(kind=Job.Kind.NEWS)[:100]
        return Response(JobListSerializer(jobs, many=True, context={"request": request}).data)

    @extend_schema(tags=["news"], request=NewsCaseSerializer, responses={202: JobListSerializer},
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
                   summary="Submit a news verification case")
    @idempotent()
    def post(self, request: Request) -> Response:
        ser = NewsCaseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data.pop("media_ids")
        media = list(MediaObject.objects.filter(owner=request.user, pk__in=ids))
        if len(media) != len(set(ids)):
            raise ApiError("Unknown media in media_ids.")
        locale = ser.validated_data.pop("locale", None) or getattr(request.user, "locale", "en")
        source = "api" if hasattr(getattr(request, "auth", None), "prefix") else "web"
        job = create_news_job(request.user, ser.validated_data, media, source=source,
                              api_key=getattr(request, "auth", None), locale=locale)
        return Response(JobListSerializer(job, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)


class NewsCaseDetailView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=["news"], responses=schemas.NewsCaseDetailSerializer,
                   summary="News case detail with the verification report")
    def get(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request).filter(kind=Job.Kind.NEWS), pk=pk)
        data = JobDetailSerializer(job, context={"request": request}).data
        case = getattr(job, "news_case", None)
        data["case"] = case.as_input() if case else None
        data["case_media"] = [{"id": str(m.pk), "name": m.original_name, "media_type": m.media_type,
                               "thumbnail_url": f"/api/v1/media/{m.pk}/thumbnail" if m.thumbnail_key else None}
                              for m in (case.media.all() if case else [])]
        return Response(data)
