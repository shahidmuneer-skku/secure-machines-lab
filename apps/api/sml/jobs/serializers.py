from __future__ import annotations

from typing import Any

from django.urls import reverse
from rest_framework import serializers

from sml.catalog.registry import registry
from sml.media.models import MediaObject

from .eta import queue_info
from .live import task_progress
from .models import Artifact, Explanation, Job, JobEvent, JobTask


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

    def get_content_url(self, obj: MediaObject) -> str | None:
        return f"{self._prefix()}/{obj.pk}/content" if obj.status == MediaObject.Status.READY else None

    def get_thumbnail_url(self, obj: MediaObject) -> str | None:
        return f"{self._prefix()}/{obj.pk}/thumbnail" if obj.thumbnail_key else None


class JobListSerializer(serializers.ModelSerializer):
    models = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    verdict_label = serializers.CharField(source="get_verdict_display")

    class Meta:
        model = Job
        fields = ["id", "created_at", "kind", "source", "status", "stage", "progress", "title", "media_type",
                  "thumbnail_url", "models", "audit_steps", "verdict", "verdict_label", "fake_probability",
                  "partial", "credits_quoted", "credits_charged", "queue", "started_at", "finished_at",
                  "expires_at", "batch_id", "run_number", "error_code", "error_message"]

    def get_models(self, obj: Job) -> list[dict[str, str]]:
        return _model_names(obj.models_selected, _lang(self.context))

    def get_thumbnail_url(self, obj: Job) -> str | None:
        media = obj.media
        if media is None or not media.thumbnail_key or media.status != MediaObject.Status.READY:
            return None
        return f"{self.context.get('media_url_prefix', '/api/v1/media')}/{media.pk}/thumbnail"

    def get_queue(self, obj: Job) -> dict[str, Any] | None:
        if obj.status != Job.Status.QUEUED:
            return None
        first = next((t for t in obj.tasks.all() if t.kind != JobTask.Kind.AUDIT
                      and t.status in (JobTask.Status.PENDING, JobTask.Status.DISPATCHED)), None)
        return queue_info(first) if first else None


class JobTaskSerializer(serializers.ModelSerializer):
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

    def get_name(self, obj: JobTask) -> str:
        reg = registry()
        lang = _lang(self.context)
        spec = reg.get(obj.target) or reg.long_video_models.get(obj.target) or reg.audit_steps.get(obj.target)
        return spec.name(lang) if spec else obj.target

    def get_live(self, obj: JobTask) -> dict[str, Any] | None:
        live = self.context.get("live", {}).get(str(obj.pk))
        if not live or obj.status != JobTask.Status.RUNNING:
            return None
        try:
            progress = float(live.get("progress", 0))
        except ValueError:
            progress = 0.0
        return {"progress": progress, "message": live.get("message", ""), "updated_at": live.get("updated_at")}

    def get_queue_info(self, obj: JobTask) -> dict[str, Any] | None:
        return queue_info(obj)

    def get_result(self, obj: JobTask) -> dict[str, Any]:
        r = dict(obj.result or {})
        r.pop("raw_output", None)  # never expose raw model stdout
        return r


class JobEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobEvent
        fields = ["id", "created_at", "level", "code", "message", "task", "data"]


class ArtifactSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Artifact
        fields = ["id", "kind", "label", "content_type", "size_bytes", "meta", "task", "url", "created_at"]

    def get_url(self, obj: Artifact) -> str:
        prefix = self.context.get("job_url_prefix", "/api/v1/jobs")
        return f"{prefix}/{obj.job_id}/artifacts/{obj.pk}/content"


class ExplanationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Explanation
        fields = ["id", "status", "engine", "model_name", "locale", "content", "progress_log", "credits_charged",
                  "error_message", "created_at", "started_at", "finished_at"]


class JobDetailSerializer(JobListSerializer):
    media = MediaSummarySerializer(read_only=True)
    tasks = serializers.SerializerMethodField()
    events = JobEventSerializer(many=True, read_only=True)
    artifacts = ArtifactSerializer(many=True, read_only=True)
    explanations = ExplanationSerializer(many=True, read_only=True)
    reports = serializers.SerializerMethodField()

    class Meta(JobListSerializer.Meta):
        fields = [*JobListSerializer.Meta.fields, "media", "options", "locale", "summary", "verdict_reasons",
                  "quote_lines", "tasks", "events", "artifacts", "explanations", "reports", "parent",
                  "cancel_requested"]

    def get_tasks(self, obj: Job) -> list[dict[str, Any]]:
        tasks = list(obj.tasks.all())
        running = [str(t.pk) for t in tasks if t.status == JobTask.Status.RUNNING]
        ctx = {**self.context, "live": task_progress(running)}
        return JobTaskSerializer(tasks, many=True, context=ctx).data

    def get_reports(self, obj: Job) -> list[dict[str, Any]]:
        from sml.reports.serializers import ReportSerializer

        return ReportSerializer(obj.reports.all(), many=True, context=self.context).data


class JobCreateSerializer(serializers.Serializer):
    media_id = serializers.UUIDField(required=False)
    media_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=50)
    module = serializers.ChoiceField(choices=["detect", "long_video"], default="detect")
    models = serializers.ListField(child=serializers.CharField(max_length=64), required=False, allow_empty=True,
                                   help_text="Model ids from GET /catalog/models. Empty = default selection.")
    audit_steps = serializers.ListField(child=serializers.ChoiceField(choices=["face", "safety", "fas"]),
                                        required=False, default=list)
    locale = serializers.ChoiceField(choices=["en", "ko", "de"], required=False)
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
    models = serializers.ListField(child=serializers.DictField())
    audit_steps = serializers.ListField(child=serializers.CharField())
    balance = serializers.IntegerField()
    affordable = serializers.BooleanField()


def job_detail_url(job: Job) -> str:
    return reverse("job-detail", args=[job.pk])
