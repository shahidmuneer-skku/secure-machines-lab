from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sml.apikeys.permissions import require_scope
from sml.jobs.views import user_jobs
from sml.media.views import serve_object

from .models import Report
from .serializers import ReportRequestSerializer, ReportSerializer
from .services import CONTENT_TYPES, request_report


class JobReportsView(APIView):
    permission_classes = [IsAuthenticated, require_scope("reports:read")]

    @extend_schema(tags=["reports"], request=ReportRequestSerializer, responses={202: ReportSerializer},
                   summary="Generate a report (PDF / HWP / CSV / ZIP) in EN, KO or DE")
    def post(self, request: Request, pk: str) -> Response:
        job = get_object_or_404(user_jobs(request), pk=pk)
        ser = ReportRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        locale = ser.validated_data.get("locale") or job.locale
        report = request_report(job, request.user, ser.validated_data["format"], locale)
        return Response(ReportSerializer(report).data, status=status.HTTP_202_ACCEPTED)


class ReportListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    queryset = Report.objects.none()
    permission_classes = [IsAuthenticated, require_scope("reports:read")]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        qs = Report.objects.filter(job__user=self.request.user, job__deleted_at__isnull=True).select_related("job")
        fmt = self.request.query_params.get("format")
        return qs.filter(format=fmt) if fmt else qs

    @extend_schema(tags=["reports"], summary="Report library (newest first)")
    def get(self, request: Request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        return super().get(request, *args, **kwargs)


class ReportDownloadView(APIView):
    permission_classes = [IsAuthenticated, require_scope("reports:read")]

    @extend_schema(tags=["reports"], responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
                   summary="Download a generated report")
    def get(self, request: Request, pk: str) -> HttpResponse:
        report = get_object_or_404(Report.objects.select_related("job"), pk=pk, job__user=request.user,
                                   status=Report.Status.READY)
        return serve_object(report.storage_key, content_type=CONTENT_TYPES[report.format],
                            filename=report.filename, inline=False)
