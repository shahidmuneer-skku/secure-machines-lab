from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from sml.jobs.errors import user_message
from sml.jobs.eta import queue_info
from sml.jobs.live import task_progress
from sml.jobs.models import Job, JobTask
from sml.jobs.serializers import PublicQueueSerializer
from sml.media.models import MediaObject

from .registry import MODES, registry


class StudioJobCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=MODES)
    prompt = serializers.CharField(max_length=10_000)
    negative_prompt = serializers.CharField(max_length=10_000, required=False, allow_blank=True, default="")
    aspect_ratio = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    steps = serializers.IntegerField(required=False, allow_null=True, default=None)
    guidance = serializers.FloatField(required=False, allow_null=True, default=None)
    seed = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=0)
    count = serializers.IntegerField(required=False, default=1, min_value=1, max_value=8)
    transparent = serializers.BooleanField(required=False, default=False)
    reference_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=16)
    consent = serializers.BooleanField(required=False, default=False,
                                       help_text="The user confirms having the consent of the people shown.")
    model = serializers.CharField(max_length=64, required=False, allow_blank=True, default="",
                                  help_text="Administrators only: try another studio model.")


class StudioImageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    url = serializers.CharField()
    download_url = serializers.CharField()
    thumbnail_url = serializers.CharField(allow_null=True)
    width = serializers.IntegerField(allow_null=True)
    height = serializers.IntegerField(allow_null=True)
    seed = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()


class StudioLiveSerializer(serializers.Serializer):
    progress = serializers.FloatField()
    message = serializers.CharField(allow_blank=True)


class StudioParamsSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    negative_prompt = serializers.CharField(allow_null=True)
    aspect_ratio = serializers.CharField(allow_null=True)
    width = serializers.IntegerField(allow_null=True)
    height = serializers.IntegerField(allow_null=True)
    steps = serializers.IntegerField(allow_null=True)
    guidance = serializers.FloatField(allow_null=True)
    seed = serializers.IntegerField(allow_null=True)
    count = serializers.IntegerField()
    transparent = serializers.BooleanField(allow_null=True)


class StudioErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class StudioModelRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class StudioJobSerializer(serializers.ModelSerializer):
    """A studio job as its owner sees it: request, live progress, the images and the cost."""

    mode = serializers.SerializerMethodField()
    params = serializers.SerializerMethodField()
    references = serializers.SerializerMethodField()
    outputs = serializers.SerializerMethodField()
    blocked = serializers.SerializerMethodField()
    live = serializers.SerializerMethodField()
    queue = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    model = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ["id", "status", "mode", "title", "params", "references", "outputs", "blocked", "progress", "live",
                  "queue", "credits_quoted", "credits_charged", "error", "model", "created_at", "started_at",
                  "finished_at"]

    def _params(self, obj: Job) -> dict[str, Any]:
        return obj.options.get("studio") or {}

    @extend_schema_field(serializers.ChoiceField(choices=MODES))
    def get_mode(self, obj: Job) -> str:
        return str(self._params(obj).get("mode", "generate"))

    @extend_schema_field(StudioParamsSerializer)
    def get_params(self, obj: Job) -> dict[str, Any]:
        p = self._params(obj)
        return {k: p.get(k) for k in ("prompt", "negative_prompt", "aspect_ratio", "width", "height", "steps",
                                      "guidance", "seed", "count", "transparent")}

    @staticmethod
    def _image(media: MediaObject, seed: Any = None) -> dict[str, Any]:
        base = f"/api/v1/media/{media.pk}"
        return {"id": str(media.pk), "url": f"{base}/content", "download_url": f"{base}/content?download=1",
                "thumbnail_url": f"{base}/thumbnail" if media.thumbnail_key else None, "width": media.width,
                "height": media.height, "seed": seed, "name": media.original_name}

    @extend_schema_field(StudioImageSerializer(many=True))
    def get_references(self, obj: Job) -> list[dict[str, Any]]:
        ids = self._params(obj).get("references") or []
        found = {str(m.pk): m for m in MediaObject.objects.filter(pk__in=ids)
                 .exclude(status=MediaObject.Status.DELETED)}
        return [self._image(found[i]) for i in ids if i in found]

    @extend_schema_field(StudioImageSerializer(many=True))
    def get_outputs(self, obj: Job) -> list[dict[str, Any]]:
        summary = obj.summary.get("studio") or {}
        ids, seeds = summary.get("outputs") or [], summary.get("seeds") or []
        found = {str(m.pk): m for m in obj.outputs.exclude(status=MediaObject.Status.DELETED)}
        return [self._image(found[i], seeds[n] if n < len(seeds) else None) for n, i in enumerate(ids) if i in found]

    @extend_schema_field(OpenApiTypes.INT)
    def get_blocked(self, obj: Job) -> int:
        return int((obj.summary.get("studio") or {}).get("blocked") or 0)

    def _task(self, obj: Job) -> JobTask | None:
        return next((t for t in obj.tasks.all() if t.kind == JobTask.Kind.STUDIO), None)

    @extend_schema_field(StudioLiveSerializer(allow_null=True))
    def get_live(self, obj: Job) -> dict[str, Any] | None:
        task = self._task(obj)
        if task is None or task.status != JobTask.Status.RUNNING:
            return None
        live = task_progress([str(task.pk)]).get(str(task.pk)) or {}
        return {"progress": float(live.get("progress", task.progress) or 0), "message": live.get("message", "")}

    @extend_schema_field(PublicQueueSerializer(allow_null=True))
    def get_queue(self, obj: Job) -> dict[str, Any] | None:
        task = self._task(obj)
        info = queue_info(task) if task is not None and obj.status == Job.Status.QUEUED else None
        return PublicQueueSerializer(info).data if info else None

    @extend_schema_field(StudioErrorSerializer(allow_null=True))
    def get_error(self, obj: Job) -> dict[str, str] | None:
        if obj.status != Job.Status.FAILED:
            return None
        code = obj.error_code or "STUDIO_FAILED"
        return {"code": code, "message": obj.error_message or user_message(code)}

    @extend_schema_field(StudioModelRefSerializer(allow_null=True))
    def get_model(self, obj: Job) -> dict[str, str] | None:
        """Staff only (users never see which model made their image)."""
        if not self.context.get("staff"):
            return None
        model_id = (obj.models_selected or [""])[0]
        model = registry().get(model_id)
        return {"id": model_id, "name": model.name if model else model_id}


# --- configuration (what the studio page adapts to) -------------------------------------------------

class StudioRangeSerializer(serializers.Serializer):
    default = serializers.FloatField()
    min = serializers.FloatField()
    max = serializers.FloatField()
    step = serializers.FloatField(required=False)


class StudioReferenceLimitSerializer(serializers.Serializer):
    min = serializers.IntegerField()
    max = serializers.IntegerField()


class StudioAspectRatioSerializer(serializers.Serializer):
    id = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()


class StudioControlsSerializer(serializers.Serializer):
    references = StudioReferenceLimitSerializer()
    aspect_ratios = StudioAspectRatioSerializer(many=True)
    match_input = serializers.BooleanField()
    negative_prompt = serializers.BooleanField()
    transparent = serializers.BooleanField()
    steps = StudioRangeSerializer(allow_null=True)
    guidance = StudioRangeSerializer(allow_null=True)
    max_outputs = serializers.IntegerField()
    prompt_max_chars = serializers.IntegerField()


class StudioModeSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    price = serializers.IntegerField(help_text="Credits per delivered image.")
    controls = StudioControlsSerializer(allow_null=True)


class StudioModesSerializer(serializers.Serializer):
    generate = StudioModeSerializer()
    edit = StudioModeSerializer()


class StudioModelInfoSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    vendor = serializers.CharField()
    license = serializers.CharField()
    commercial = serializers.BooleanField()
    modes = serializers.ListField(child=serializers.ChoiceField(choices=MODES))
    installed = serializers.BooleanField()
    loaded = serializers.BooleanField()
    controls = serializers.DictField(child=StudioControlsSerializer())
    weights_gb = serializers.FloatField(required=False, allow_null=True)


class StudioActiveSerializer(serializers.Serializer):
    generate = serializers.CharField(allow_null=True)
    edit = serializers.CharField(allow_null=True)


class StudioConfigSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    online = serializers.BooleanField()
    modes = StudioModesSerializer()
    consent_statement = serializers.CharField()
    consent_version = serializers.CharField()
    models = StudioModelInfoSerializer(many=True, required=False, help_text="Administrators only.")
    active = StudioActiveSerializer(required=False, help_text="Administrators only.")


class StudioServerSerializer(serializers.Serializer):
    state = serializers.CharField()
    gpu = serializers.CharField(required=False)
    loaded = serializers.ListField(child=serializers.CharField(), required=False)
    loading = serializers.CharField(allow_null=True, required=False)
    busy = serializers.BooleanField(required=False)
    waiting = serializers.IntegerField(required=False)
    device_free_gb = serializers.FloatField(allow_null=True, required=False)
    budget_gb = serializers.FloatField(allow_null=True, required=False)


class StudioPricesSerializer(serializers.Serializer):
    generate = serializers.IntegerField()
    edit = serializers.IntegerField()


class StudioAdminSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    generate_model = serializers.CharField(allow_blank=True)
    edit_model = serializers.CharField(allow_blank=True)
    prices = StudioPricesSerializer()
    server = StudioServerSerializer()
    models = StudioModelInfoSerializer(many=True)


class StudioAdminUpdateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    generate_model = serializers.CharField(required=False, allow_blank=True, max_length=64)
    edit_model = serializers.CharField(required=False, allow_blank=True, max_length=64)
