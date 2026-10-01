from __future__ import annotations

from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics, status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml import api_schemas as schemas
from sml.apikeys.permissions import require_scope
from sml.core.exceptions import ApiError, Conflict
from sml.core.idempotency import idempotent
from sml.core.permissions import require
from sml.core.throttling import JobCreateThrottle
from sml.credits.services import get_balance
from sml.media import services as media_services
from sml.media.models import MediaObject
from sml.media.views import serve_object

from . import explain, public, services
from .models import Artifact, Job, JobTask
from .serializers import (
    ExplanationSerializer,
    JobCreateSerializer,
    JobDetailSerializer,
    JobListSerializer,
    QuoteResponseSerializer,
)


def user_jobs(request: Request):  # type: ignore[no-untyped-def]
    return (Job.objects.filter(user=request.user, deleted_at__isnull=True)
            .select_related("media")
            .prefetch_related(Prefetch("tasks", queryset=JobTask.objects.order_by("created_at"))))


def _source(request: Request) -> str:
    return "api" if hasattr(getattr(request, "auth", None), "prefix") else "web"


def _requests_from(request: Request, data: dict) -> list[services.JobRequest]:
    ids = data.get("media_ids") or [data["media_id"]]
    media_qs = MediaObject.objects.filter(owner=request.user, pk__in=ids)
    found = {str(m.pk): m for m in media_qs}
    missing = [str(i) for i in ids if str(i) not in found]
    if missing:
        raise ApiError(f"Unknown media: {', '.join(missing)}", extra={"media_ids": missing})
    locale = data.get("locale") or getattr(request.user, "locale", "en")
    return [services.JobRequest(media=found[str(i)], module=data["module"], options=data.get("options") or {},
                                locale=locale) for i in ids]


class JobFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Job.Status.choices)
    kind = filters.MultipleChoiceFilter(choices=Job.Kind.choices)
    verdict = filters.MultipleChoiceFilter(choices=Job.Verdict.choices)
    media_type = filters.ChoiceFilter(choices=[("image", "image"), ("video", "video")])
    source = filters.ChoiceFilter(choices=Job.Source.choices)
    q = filters.CharFilter(method="filter_q")
    created_after = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lt")
    batch = filters.UUIDFilter(field_name="batch_id")

    class Meta:
        model = Job
        fields: list[str] = []

    def filter_q(self, qs, name, value):  # type: ignore[no-untyped-def]
        cond = Q(title__icontains=value)
        try:
            import uuid

            cond |= Q(pk=uuid.UUID(value))
        except ValueError:
            pass
        return qs.filter(cond)


class JobListCreateView(generics.ListAPIView):
    serializer_class = JobListSerializer
    queryset = Job.objects.none()
    filterset_class = JobFilter
    parser_classes = [JSONParser]

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [IsAuthenticated(), require_scope("detect:write")(), require("run_detection")()]
        return [IsAuthenticated(), require_scope("jobs:read")()]

    def get_throttles(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            return [JobCreateThrottle(), *super().get_throttles()]
        return super().get_throttles()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = user_jobs(self.request)
        # Image studio jobs have their own history (/studio/jobs) unless asked for by kind.
        if Job.Kind.STUDIO not in self.request.query_params.getlist("kind"):
            qs = qs.exclude(kind=Job.Kind.STUDIO)
        return qs

    @extend_schema(tags=["jobs"], summary="List my jobs (newest first, cursor-paginated)")
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["jobs"], request=JobCreateSerializer, responses={202: schemas.JobCreatedSerializer},
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
        summary="Create detection job(s) for uploaded media. Returns 202 immediately; follow progress via SSE.",
    )
    @idempotent()
    def post(self, request: Request) -> Response:
        ser = JobCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reqs = _requests_from(request, ser.validated_data)
        api_key = getattr(request, "auth", None)
        if len(reqs) == 1:
            jobs = [services.create_job(request.user, reqs[0], source=_source(request), api_key=api_key)]
        else:
            _, jobs = services.create_batch(request.user, reqs, source=_source(request), api_key=api_key,
                                            name=ser.validated_data.get("batch_name", ""))
        data = JobListSerializer(jobs, many=True, context={"request": request}).data
        return Response({"jobs": data}, status=status.HTTP_202_ACCEPTED)


class QuoteView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write")]

    @extend_schema(tags=["jobs"], request=JobCreateSerializer, responses=QuoteResponseSerializer,
                   summary="Price a request before submitting it (no side effects)")
    def post(self, request: Request) -> Response:
        ser = JobCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reqs = _requests_from(request, ser.validated_data)
        prepared = [services.prepare(request.user, r) for r in reqs]
        total = sum(p.quote.credits for p in prepared)
        lines = [{"label": f"{p.request.media.original_name}: {ln.label}", "credits": ln.credits}
                 for p in prepared for ln in p.quote.lines]
        balance = get_balance(request.user)
        return Response({"credits": total, "lines": lines, "balance": balance.balance,
                         "affordable": balance.unlimited or balance.balance >= total})


class DetectView(APIView):
    """One-call API: upload + create job. Ideal for scripts and API clients."""

    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated, require_scope("detect:write"), require("run_detection")]
    throttle_classes = [JobCreateThrottle]

    @extend_schema(
        tags=["jobs"],
        request={"multipart/form-data": {"type": "object", "required": ["file"], "properties": {
            "file": {"type": "string", "format": "binary"},
            "module": {"type": "string", "enum": ["detect", "long_video"]},
        }}},
        responses={202: JobListSerializer},
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
        summary="Upload a file and start detection in one request",
    )
    @idempotent()
    def post(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            raise ApiError("Send the file in a multipart field named 'file'.")
        media = media_services.ingest_file(upload, original_name=upload.name, owner=request.user)
        req = services.JobRequest(media=media, module=request.data.get("module") or "detect",
                                  locale=getattr(request.user, "locale", "en"))
        job = services.create_job(request.user, req, source=_source(request), api_key=getattr(request, "auth", None))
        return Response(JobListSerializer(job, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)


class JobDetailView(APIView):
    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "DELETE":
            return [IsAuthenticated(), require_scope("jobs:write")()]
        return [IsAuthenticated(), require_scope("jobs:read")()]

    @extend_schema(tags=["jobs"], responses=JobDetailSerializer,
                   summary="Job detail: tasks with live progress, queue position, timeline, artifacts, verdict")
    def get(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request).prefetch_related("events", "artifacts", "explanations"), pk=pk)
        return Response(JobDetailSerializer(job, context={"request": request}).data)

    @extend_schema(tags=["jobs"], responses={204: None},
                   summary="Delete a job: media and artifacts are purged now; billing history is kept")
    def delete(self, request: Request, pk: str) -> Response:
        services.delete_job(get_object_or_404(user_jobs(request), pk=pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobCancelView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:write")]

    @extend_schema(tags=["jobs"], request=None, responses=JobListSerializer,
                   summary="Cancel: queued work stops immediately (full refund); running work best-effort")
    def post(self, request: Request, pk: str) -> Response:
        job = services.cancel_job(get_object_or_404(user_jobs(request), pk=pk))
        return Response(JobListSerializer(job, context={"request": request}).data)


class JobBulkCancelView(APIView):
    """Cancel several of your jobs at once (e.g. every job still queued or running)."""

    permission_classes = [IsAuthenticated, require_scope("jobs:write")]

    @extend_schema(tags=["jobs"], request=schemas.JobBulkCancelSerializer,
                   responses=schemas.JobBulkCancelResultSerializer,
                   summary="Cancel several jobs: queued work stops at once (refunded); running work best-effort")
    def post(self, request: Request) -> Response:
        body = schemas.JobBulkCancelSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ids = list(dict.fromkeys(body.validated_data["ids"]))
        jobs = {j.pk: j for j in user_jobs(request).filter(pk__in=ids)}
        out: dict[str, list[str]] = {"canceled": [], "already_finished": [], "not_found": []}
        for job_id in ids:
            job = jobs.get(job_id)
            if job is None:
                out["not_found"].append(str(job_id))
            elif job.is_terminal:
                out["already_finished"].append(str(job_id))
            else:
                try:
                    services.cancel_job(job)
                    out["canceled"].append(str(job_id))
                except Conflict:  # finished while we were cancelling the others
                    out["already_finished"].append(str(job_id))
        return Response(out)


class JobRerunView(APIView):
    permission_classes = [IsAuthenticated, require_scope("detect:write"), require("run_detection")]

    @extend_schema(tags=["jobs"], request=None, responses={202: JobListSerializer},
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=False)],
                   summary="Re-run a finished job with the same settings (charged again)")
    @idempotent(required=False)
    def post(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request), pk=pk)
        new = services.rerun_job(job, user=request.user, source=_source(request),
                                 api_key=getattr(request, "auth", None))
        return Response(JobListSerializer(new, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)


class ArtifactContentView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read")]

    @extend_schema(tags=["jobs"], responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
                   summary="Download a heatmap, face crop or annotated video listed in the job's artifacts")
    def get(self, request: Request, pk: str, artifact_id: str) -> HttpResponse:
        job = get_object_or_404(user_jobs(request), pk=pk)
        art = get_object_or_404(Artifact, pk=artifact_id, job=job)
        if not public.is_downloadable(job, art):
            raise Http404
        return serve_object(art.storage_key, content_type=art.content_type, filename=public.artifact_filename(art))


class ExplainView(APIView):
    permission_classes = [IsAuthenticated, require_scope("jobs:read"), require("use_reasoning")]

    @extend_schema(tags=["jobs"], responses=ExplanationSerializer(many=True), summary="Explanations for a job")
    def get(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request), pk=pk)
        return Response(ExplanationSerializer(job.explanations.all(), many=True).data)

    @extend_schema(tags=["jobs"], request=None, responses={202: ExplanationSerializer},
                   parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=False)],
                   summary="Ask the reasoning agent why this file was judged fake or real (costs credits)")
    @idempotent(required=False)
    def post(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request), pk=pk)
        locale = request.data.get("locale") if isinstance(request.data, dict) else None
        exp = explain.request_explanation(job, request.user, locale or getattr(request.user, "locale", "en"))
        return Response(ExplanationSerializer(exp).data, status=status.HTTP_202_ACCEPTED)
