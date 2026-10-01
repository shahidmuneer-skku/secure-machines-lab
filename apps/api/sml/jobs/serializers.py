from __future__ import annotations

from typing import Any

from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from sml.accounts.models import User
from sml.catalog.registry import registry
from sml.media.models import MediaObject
from sml.reports.serializers import ReportSerializer

from . import public
from .eta import queue_info
from .live import task_progress
from .models import Artifact, Explanation, Job, JobEvent, JobTask


class ModelRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class QueueInfoSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    consumers = serializers.IntegerField()
    eta_seconds = serializers.IntegerField()
    workers_online = serializers.BooleanField()


class LiveProgressSerializer(serializers.Serializer):
    progress = serializers.FloatField()
    message = serializers.CharField(allow_blank=True)
    updated_at = serializers.CharField(allow_null=True)


def _model_names(ids: list[str], lang: str) -> list[dict[str, str]]:
    reg = registry()
    out = []
    for mid in ids:
        spec = reg.get(mid) or reg.long_video_models.get(mid)
        out.append({"id": mid, "name": spec.name(lang) if spec else mid})
    return out


def _lang(context: dict[str, Any]) -> str:
    request = context.get("request")
    user = getattr(request, "user", None)
    return getattr(user, "locale", None) or context.get("lang", "en")


def _thumbnail_url(obj: Job, context: dict[str, Any]) -> str | None:
    media = obj.media
    if media is None and (obj.options or {}).get("stream"):
        # Streamed long-form scans keep no media, only a preview frame.
        preview = next((a for a in obj.artifacts.all() if (a.meta or {}).get("preview")), None)
        return f"/api/v1/jobs/{obj.pk}/artifacts/{preview.pk}/content" if preview else None
    if media is None or not media.thumbnail_key or media.status != MediaObject.Status.READY:
        return None
    return f"{context.get('media_url_prefix', '/api/v1/media')}/{media.pk}/thumbnail"


def _queue_info(obj: Job) -> dict[str, Any] | None:
    """Queue position of the job's first waiting analysis task."""
    if obj.status != Job.Status.QUEUED:
        return None
    first = next((t for t in obj.tasks.all() if t.kind != JobTask.Kind.AUDIT
                  and t.status in (JobTask.Status.PENDING, JobTask.Status.DISPATCHED)), None)
    return queue_info(first) if first else None


class MediaSummarySerializer(serializers.ModelSerializer):
    content_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaObject
        fields = ["id", "media_type", "original_name", "content_type", "size_bytes", "sha256", "width",
                  "height", "duration_seconds", "fps", "frame_count", "codec", "status", "expires_at",
                  "content_url", "thumbnail_url"]

    def _prefix(self) -> str:
        return self.context.get("media_url_prefix", "/api/v1/media")

    @extend_schema_field(OpenApiTypes.STR)
    def get_content_url(self, obj: MediaObject) -> str | None:
        return f"{self._prefix()}/{obj.pk}/content" if obj.status == MediaObject.Status.READY else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_thumbnail_url(self, obj: MediaObject) -> str | None:
        return f"{self._prefix()}/{obj.pk}/thumbnail" if obj.thumbnail_key else None


class AdminJobListSerializer(serializers.ModelSerializer):
    """Operator view: detectors, checks and raw results. Admin endpoints only."""

    models = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    verdict_label = serializers.CharField(source="get_verdict_display")
    ai_generated = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ["id", "created_at", "kind", "source", "status", "stage", "progress", "title", "media_type",
                  "thumbnail_url", "models", "audit_steps", "verdict", "verdict_label", "ai_generated",
                  "fake_probability",
                  "partial", "credits_quoted", "credits_charged", "queue", "started_at", "finished_at",
                  "expires_at", "batch_id", "run_number", "error_code", "error_message"]

    @extend_schema_field(ModelRefSerializer(many=True))
    def get_models(self, obj: Job) -> list[dict[str, str]]:
        return _model_names(obj.models_selected, _lang(self.context))

    @extend_schema_field(OpenApiTypes.STR)
    def get_thumbnail_url(self, obj: Job) -> str | None:
        return _thumbnail_url(obj, self.context)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_ai_generated(self, obj: Job) -> bool:
        return public.ai_generated(obj)

    @extend_schema_field(QueueInfoSerializer(allow_null=True))
    def get_queue(self, obj: Job) -> dict[str, Any] | None:
        return _queue_info(obj)


class AdminJobTaskSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display")
    live = serializers.SerializerMethodField()
    queue_info = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = JobTask
        fields = ["id", "kind", "target", "name", "status", "status_label", "attempt", "progress",
                  "stage_message", "dispatched_at", "started_at", "finished_at", "duration_ms", "gpu",
                  "error_code", "error_message", "fallback_for", "live", "queue_info", "result"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, obj: JobTask) -> str:
        reg = registry()
        lang = _lang(self.context)
        spec = reg.get(obj.target) or reg.long_video_models.get(obj.target) or reg.audit_steps.get(obj.target)
        return spec.name(lang) if spec else obj.target

    @extend_schema_field(LiveProgressSerializer(allow_null=True))
    def get_live(self, obj: JobTask) -> dict[str, Any] | None:
        live = self.context.get("live", {}).get(str(obj.pk))
        if not live or obj.status != JobTask.Status.RUNNING:
            return None
        try:
            progress = float(live.get("progress", 0))
        except ValueError:
            progress = 0.0
        return {"progress": progress, "message": live.get("message", ""), "updated_at": live.get("updated_at")}

    @extend_schema_field(QueueInfoSerializer(allow_null=True))
    def get_queue_info(self, obj: JobTask) -> dict[str, Any] | None:
        return queue_info(obj)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_result(self, obj: JobTask) -> dict[str, Any]:
        r = dict(obj.result or {})
        r.pop("raw_output", None)  # never expose raw model stdout
        return r


class AdminJobEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobEvent
        fields = ["id", "created_at", "level", "code", "message", "public_message", "task", "data"]


class AdminArtifactSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Artifact
        fields = ["id", "kind", "label", "content_type", "size_bytes", "meta", "task", "url", "created_at"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_url(self, obj: Artifact) -> str:
        prefix = self.context.get("job_url_prefix", "/api/v1/jobs")
        return f"{prefix}/{obj.job_id}/artifacts/{obj.pk}/content"


class AdminExplanationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Explanation
        fields = ["id", "status", "engine", "model_name", "locale", "content", "progress_log", "credits_charged",
                  "error_message", "created_at", "started_at", "finished_at"]


class AdminJobDetailSerializer(AdminJobListSerializer):
    media = MediaSummarySerializer(read_only=True)
    tasks = serializers.SerializerMethodField()
    events = AdminJobEventSerializer(many=True, read_only=True)
    artifacts = AdminArtifactSerializer(many=True, read_only=True)
    explanations = AdminExplanationSerializer(many=True, read_only=True)
    reports = serializers.SerializerMethodField()

    class Meta(AdminJobListSerializer.Meta):
        fields = [*AdminJobListSerializer.Meta.fields, "media", "options", "locale", "summary", "verdict_reasons",
                  "quote_lines", "tasks", "events", "artifacts", "explanations", "reports", "parent",
                  "cancel_requested", "purged_at"]

    @extend_schema_field(AdminJobTaskSerializer(many=True))
    def get_tasks(self, obj: Job) -> list[dict[str, Any]]:
        tasks = list(obj.tasks.all())
        running = [str(t.pk) for t in tasks if t.status == JobTask.Status.RUNNING]
        ctx = {**self.context, "live": task_progress(running)}
        return AdminJobTaskSerializer(tasks, many=True, context=ctx).data

    @extend_schema_field(ReportSerializer(many=True))
    def get_reports(self, obj: Job) -> list[dict[str, Any]]:
        return ReportSerializer(obj.reports.all(), many=True, context=self.context).data


class JobCreateSerializer(serializers.Serializer):
    """Detectors and checks are chosen by the administrator, not by the caller."""

    media_id = serializers.UUIDField(required=False)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=50)
    module = serializers.ChoiceField(choices=["detect", "long_video"], default="detect")
    locale = serializers.ChoiceField(choices=User.Locale.choices, required=False)
    batch_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    options = serializers.DictField(required=False, default=dict)

    def validate_options(self, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"interval_seconds"}
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(f"Unknown options: {', '.join(sorted(unknown))}")
        if "interval_seconds" in value:
            try:
                iv = float(value["interval_seconds"])
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError("interval_seconds must be a number") from exc
            if not 1 <= iv <= 60:
                raise serializers.ValidationError("interval_seconds must be between 1 and 60")
            value["interval_seconds"] = iv
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("media_id") and not attrs.get("media_ids"):
            raise serializers.ValidationError("Provide media_id or media_ids.")
        return attrs


class QuoteResponseSerializer(serializers.Serializer):
    credits = serializers.IntegerField()
    lines = serializers.ListField(child=serializers.DictField())
    balance = serializers.IntegerField()
    affordable = serializers.BooleanField()


# --- user view (web app and public API): verdict and evidence, never the detectors ---------------

class PublicQueueSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    eta_seconds = serializers.IntegerField()
    workers_online = serializers.BooleanField()


class JobListSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    verdict_label = serializers.SerializerMethodField()
    ai_generated = serializers.SerializerMethodField(
        help_text="True when AI-generation markers in the file's metadata flag it as likely AI-generated.")

    class Meta:
        model = Job
        fields = ["id", "created_at", "kind", "source", "status", "stage", "progress", "title", "media_type",
                  "thumbnail_url", "verdict", "verdict_label", "ai_generated", "fake_probability", "partial",
                  "credits_quoted", "credits_charged", "queue", "started_at", "finished_at", "expires_at",
                  "batch_id", "run_number", "error_code", "error_message"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_thumbnail_url(self, obj: Job) -> str | None:
        return _thumbnail_url(obj, self.context)

    @extend_schema_field(PublicQueueSerializer(allow_null=True))
    def get_queue(self, obj: Job) -> dict[str, Any] | None:
        return public.queue(_queue_info(obj))

    @extend_schema_field(OpenApiTypes.STR)
    def get_verdict_label(self, obj: Job) -> str:
        return "Likely AI-generated" if public.ai_generated(obj) else obj.get_verdict_display()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_ai_generated(self, obj: Job) -> bool:
        return public.ai_generated(obj)


class JobStepSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=["queued", "checks", "analysis", "verification", "results"])
    status = serializers.CharField()
    progress = serializers.FloatField()


class EvidenceSerializer(serializers.Serializer):
    source = serializers.CharField()
    detail = serializers.CharField()
    strength = serializers.CharField(allow_blank=True)


class ProvenanceSerializer(serializers.Serializer):
    ai_generated = serializers.BooleanField()
    confidence = serializers.CharField()
    c2pa_status = serializers.CharField()
    camera = serializers.CharField(allow_null=True)
    software = serializers.CharField(allow_null=True)
    evidence = EvidenceSerializer(many=True)
    notes = serializers.ListField(child=serializers.CharField())


class CheckSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=["face", "safety", "fas"])
    status = serializers.CharField()
    result = serializers.DictField(help_text="faces_found, sensitive_content or spoof_detected")


class AnalysisResultSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=["face_swap", "ai_generated", "general"])
    status = serializers.ChoiceField(choices=["done", "no_face", "failed"])
    verdict = serializers.CharField(allow_blank=True)
    fake_probability = serializers.FloatField(allow_null=True)


class TimelinePointSerializer(serializers.Serializer):
    analysis = serializers.ChoiceField(choices=["face_swap", "ai_generated", "general"])
    start_sec = serializers.FloatField()
    end_sec = serializers.FloatField()
    fake_prob = serializers.FloatField()


class LongVideoSummarySerializer(serializers.Serializer):
    status = serializers.CharField()
    analysed_seconds = serializers.FloatField(allow_null=True)
    range_seconds = serializers.FloatField(allow_null=True)
    duration_seconds = serializers.FloatField(allow_null=True)
    range = serializers.ListField(child=serializers.FloatField(allow_null=True), allow_null=True)


class NewsReportSerializer(serializers.Serializer):
    status = serializers.CharField(allow_null=True)
    confidence = serializers.FloatField(allow_null=True)
    report_markdown = serializers.CharField(allow_blank=True)
    meta = serializers.DictField()


class JobEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    level = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()
    data = serializers.DictField()


class ArtifactSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=["heatmap", "face", "video"])
    label = serializers.ChoiceField(choices=["heatmap", "face", "video"])
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    url = serializers.CharField()
    created_at = serializers.DateTimeField()


class ExplanationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Explanation
        fields = ["id", "status", "locale", "content", "credits_charged", "error_message", "created_at",
                  "started_at", "finished_at"]


class JobDetailSerializer(JobListSerializer):
    media = MediaSummarySerializer(read_only=True)
    options = serializers.SerializerMethodField()
    verdict_reasons = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()
    analyses = serializers.SerializerMethodField()
    provenance = serializers.SerializerMethodField()
    checks = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    long_video = serializers.SerializerMethodField()
    news = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    artifacts = serializers.SerializerMethodField()
    explanations = ExplanationSerializer(many=True, read_only=True)
    reports = serializers.SerializerMethodField()

    class Meta(JobListSerializer.Meta):
        fields = [*JobListSerializer.Meta.fields, "media", "options", "locale", "verdict_reasons", "quote_lines",
                  "steps", "analyses", "provenance", "checks", "timeline", "long_video", "news", "events", "artifacts",
                  "explanations", "reports", "parent", "cancel_requested", "purged_at"]

    def _tasks(self, obj: Job) -> list[JobTask]:
        cache = self.context.setdefault("_tasks", {})
        if obj.pk not in cache:
            cache[obj.pk] = list(obj.tasks.all())
        return cache[obj.pk]

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_options(self, obj: Job) -> dict[str, Any]:
        return public.options(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_verdict_reasons(self, obj: Job) -> list[dict[str, Any]]:
        return public.reasons(obj)

    @extend_schema_field(JobStepSerializer(many=True))
    def get_steps(self, obj: Job) -> list[dict[str, Any]]:
        tasks = self._tasks(obj)
        running = [str(t.pk) for t in tasks if t.status == JobTask.Status.RUNNING]
        return public.steps(obj, tasks, task_progress(running))

    @extend_schema_field(AnalysisResultSerializer(many=True))
    def get_analyses(self, obj: Job) -> list[dict[str, Any]]:
        return public.analyses(obj)

    @extend_schema_field(ProvenanceSerializer(allow_null=True))
    def get_provenance(self, obj: Job) -> dict[str, Any] | None:
        return public.provenance(self._tasks(obj))

    @extend_schema_field(CheckSerializer(many=True))
    def get_checks(self, obj: Job) -> list[dict[str, Any]]:
        return public.checks(self._tasks(obj))

    @extend_schema_field(TimelinePointSerializer(many=True))
    def get_timeline(self, obj: Job) -> list[dict[str, Any]]:
        return public.timeline(obj, self._tasks(obj))

    @extend_schema_field(LongVideoSummarySerializer(allow_null=True))
    def get_long_video(self, obj: Job) -> dict[str, Any] | None:
        return public.long_video(obj, self._tasks(obj))

    @extend_schema_field(NewsReportSerializer(allow_null=True))
    def get_news(self, obj: Job) -> dict[str, Any] | None:
        return public.news(obj)

    @extend_schema_field(JobEventSerializer(many=True))
    def get_events(self, obj: Job) -> list[dict[str, Any]]:
        return public.events(obj)

    @extend_schema_field(ArtifactSerializer(many=True))
    def get_artifacts(self, obj: Job) -> list[dict[str, Any]]:
        return public.artifacts(obj, self.context.get("job_url_prefix", "/api/v1/jobs"), self._tasks(obj))

    @extend_schema_field(ReportSerializer(many=True))
    def get_reports(self, obj: Job) -> list[dict[str, Any]]:
        return ReportSerializer(obj.reports.all(), many=True, context=self.context).data


def job_detail_url(job: Job) -> str:
    return reverse("job-detail", args=[job.pk])
