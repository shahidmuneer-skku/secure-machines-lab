"""Response shapes for views that build JSON by hand.

These serializers are only used for OpenAPI generation (and therefore the typed
TypeScript client). Keep them in sync with the corresponding views.
"""

from __future__ import annotations

from rest_framework import serializers

from sml.accounts.models import AccessPolicy
from sml.accounts.serializers import MeSerializer
from sml.apikeys.serializers import ApiKeyUsageDailySerializer, ApiRequestLogSerializer
from sml.billing.models import Provider
from sml.billing.serializers import CreditPackSerializer, PlanSerializer
from sml.jobs.serializers import AdminJobDetailSerializer, JobDetailSerializer, JobListSerializer

# --- accounts ------------------------------------------------------------------------

class PublicConfigSerializer(serializers.Serializer):
    signups_enabled = serializers.BooleanField()
    maintenance_mode = serializers.BooleanField()
    announcement = serializers.CharField(allow_blank=True)
    captcha_site_key = serializers.CharField(allow_blank=True)
    captcha_enabled = serializers.BooleanField()
    billing_enabled = serializers.BooleanField()
    languages = serializers.ListField(child=serializers.CharField())
    guest_trial_enabled = serializers.BooleanField()


class AccessSummarySerializer(serializers.Serializer):
    modules = serializers.DictField(child=serializers.BooleanField())
    audit_steps = serializers.ListField(child=serializers.CharField())
    unlimited_credits = serializers.BooleanField()


class MeResponseSerializer(MeSerializer):
    access = AccessSummarySerializer()

    class Meta(MeSerializer.Meta):
        fields = [*MeSerializer.Meta.fields, "access"]


# --- api keys --------------------------------------------------------------------------

class ApiKeyUsageTotalsSerializer(serializers.Serializer):
    requests = serializers.IntegerField()
    errors = serializers.IntegerField()
    jobs_created = serializers.IntegerField()
    credits_spent = serializers.IntegerField()


class ApiKeyUsageResponseSerializer(serializers.Serializer):
    totals = ApiKeyUsageTotalsSerializer()
    daily = ApiKeyUsageDailySerializer(many=True)
    recent_requests = ApiRequestLogSerializer(many=True)


class IdLabelSerializer(serializers.Serializer):
    id = serializers.CharField()
    label = serializers.CharField()


# --- catalog ---------------------------------------------------------------------------

class ModuleInfoSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=AccessPolicy.MODULES)
    allowed = serializers.BooleanField()
    price = serializers.DictField(child=serializers.IntegerField())


# --- credits -----------------------------------------------------------------------------

class PriceItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    credits = serializers.IntegerField()


class FreeAllowanceSerializer(serializers.Serializer):
    guest_trial_images_per_day = serializers.IntegerField()
    signup_bonus_credits = serializers.IntegerField()
    signup_bonus_expiry_days = serializers.IntegerField()
    daily_free_credits = serializers.IntegerField()


class PriceListSerializer(serializers.Serializer):
    prices = PriceItemSerializer(many=True)
    free = FreeAllowanceSerializer()


# --- billing -------------------------------------------------------------------------------

class ProviderInfoSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=Provider.choices)
    currency = serializers.ChoiceField(choices=["KRW", "USD"])


class BillingCatalogSerializer(serializers.Serializer):
    billing_enabled = serializers.BooleanField()
    providers = ProviderInfoSerializer(many=True)
    toss_client_key = serializers.CharField(allow_blank=True)
    packs = CreditPackSerializer(many=True)
    plans = PlanSerializer(many=True)


class CheckoutResponseSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    provider = serializers.CharField()
    redirect_url = serializers.CharField(allow_null=True)
    client_params = serializers.DictField()


class UrlSerializer(serializers.Serializer):
    url = serializers.CharField()


# --- jobs / media / news / trial -------------------------------------------------------------

class JobCreatedSerializer(serializers.Serializer):
    jobs = JobListSerializer(many=True)


class TaskLogLineSerializer(serializers.Serializer):
    at = serializers.CharField()
    message = serializers.CharField()


class TaskLogSerializer(serializers.Serializer):
    task_id = serializers.UUIDField()
    status = serializers.CharField()
    lines = TaskLogLineSerializer(many=True)


class MultipartStartResponseSerializer(serializers.Serializer):
    media_id = serializers.UUIDField()
    part_size = serializers.IntegerField()
    part_urls = serializers.ListField(child=serializers.CharField())


class CaseMediaSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    media_type = serializers.CharField()
    thumbnail_url = serializers.CharField(allow_null=True)


class NewsCaseDetailSerializer(JobDetailSerializer):
    case = serializers.DictField(allow_null=True)
    case_media = CaseMediaSerializer(many=True)

    class Meta(JobDetailSerializer.Meta):
        fields = [*JobDetailSerializer.Meta.fields, "case", "case_media"]


class TrialStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    remaining = serializers.IntegerField()
    per_day = serializers.IntegerField()
    captcha_required = serializers.BooleanField()
    captcha_site_key = serializers.CharField(allow_blank=True)


class TrialDetectResponseSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    remaining = serializers.IntegerField()


# --- dashboard ----------------------------------------------------------------------------------

class DashboardKpisSerializer(serializers.Serializer):
    balance = serializers.IntegerField()
    held = serializers.IntegerField()
    unlimited = serializers.BooleanField()
    low_balance = serializers.BooleanField()
    jobs_in_period = serializers.IntegerField()
    fake_rate = serializers.FloatField(allow_null=True)
    avg_turnaround_seconds = serializers.IntegerField(allow_null=True)
    in_queue = serializers.IntegerField()
    credits_spent = serializers.IntegerField()


class JobsByDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    fake = serializers.IntegerField()
    real = serializers.IntegerField()
    other = serializers.IntegerField()


class UsageByTypeSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["image", "video", "long_video", "news"])
    jobs = serializers.IntegerField()


class CreditsByDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    spent = serializers.IntegerField()
    added = serializers.IntegerField()


class QueueWaitSerializer(serializers.Serializer):
    date = serializers.DateField()
    avg_seconds = serializers.IntegerField()


class ApiUsageTotalsSerializer(serializers.Serializer):
    requests = serializers.IntegerField()
    jobs = serializers.IntegerField()
    credits = serializers.IntegerField()


class DashboardSummarySerializer(serializers.Serializer):
    kpis = DashboardKpisSerializer()
    jobs_by_day = JobsByDaySerializer(many=True)
    usage_by_type = UsageByTypeSerializer(many=True)
    credits_by_day = CreditsByDaySerializer(many=True)
    queue_wait_by_day = QueueWaitSerializer(many=True)
    api_usage = ApiUsageTotalsSerializer()
    recent_jobs = JobListSerializer(many=True)


# --- admin (internal) ----------------------------------------------------------------------------

class OkSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class AdminOverviewSerializer(serializers.Serializer):
    users = serializers.DictField(child=serializers.IntegerField())
    jobs_24h = serializers.DictField(child=serializers.IntegerField())
    tasks_now = serializers.DictField(child=serializers.IntegerField())
    failed_tasks_24h = serializers.IntegerField()
    revenue_30d = serializers.ListField(child=serializers.DictField())
    credits_spent_30d = serializers.IntegerField()
    workers_online = serializers.IntegerField()
    gpus = serializers.ListField(child=serializers.CharField())
    maintenance_mode = serializers.BooleanField()


class RabbitQueueSerializer(serializers.Serializer):
    name = serializers.CharField()
    messages = serializers.IntegerField()
    ready = serializers.IntegerField()
    unacked = serializers.IntegerField()
    consumers = serializers.IntegerField()
    publish_rate = serializers.FloatField()
    deliver_rate = serializers.FloatField()
    idle_since = serializers.CharField(allow_null=True)


class AdminQueuesSerializer(serializers.Serializer):
    rabbitmq = RabbitQueueSerializer(many=True)
    rabbitmq_error = serializers.CharField(allow_null=True)
    tasks_by_queue = serializers.DictField(child=serializers.DictField(child=serializers.IntegerField()))
    oldest_waiting_seconds = serializers.IntegerField()


class GpuStatsSerializer(serializers.Serializer):
    name = serializers.CharField()
    util = serializers.IntegerField()
    mem_used_mb = serializers.IntegerField()
    mem_total_mb = serializers.IntegerField()
    temp_c = serializers.IntegerField()


class WorkerInfoSerializer(serializers.Serializer):
    id = serializers.CharField()
    hostname = serializers.CharField()
    pid = serializers.IntegerField()
    gpu = serializers.CharField(allow_blank=True)
    queues = serializers.ListField(child=serializers.CharField())
    started_at = serializers.CharField()
    updated_at = serializers.CharField()
    simulate = serializers.CharField()
    current_task = serializers.DictField(allow_null=True)
    gpu_stats = GpuStatsSerializer(allow_null=True)


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    latency_ms = serializers.IntegerField()


class SystemGpuSerializer(serializers.Serializer):
    host = serializers.CharField()
    index = serializers.CharField()
    workers = serializers.IntegerField(help_text="Worker processes serving models on this GPU.")
    stats = GpuStatsSerializer(allow_null=True)
    reserved_mb = serializers.IntegerField(help_text="Memory reserved by running model tasks.")
    running = serializers.IntegerField(help_text="Model tasks holding a GPU reservation.")
    waiting = serializers.IntegerField(help_text="Model tasks waiting for GPU memory.")


class StreamGpuSerializer(serializers.Serializer):
    index = serializers.CharField()
    name = serializers.CharField()
    mem_used_mb = serializers.IntegerField()
    mem_total_mb = serializers.IntegerField()
    util = serializers.IntegerField()


class SystemStreamSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    busy = serializers.BooleanField()
    waiting = serializers.IntegerField()
    model_loaded = serializers.BooleanField()
    gpu = StreamGpuSerializer(allow_null=True)
    active_sessions = serializers.IntegerField()


class LoadedLlmSerializer(serializers.Serializer):
    name = serializers.CharField()
    vram_mb = serializers.IntegerField()
    context = serializers.IntegerField(allow_null=True)
    pinned = serializers.BooleanField()


class SystemAgentsSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    loaded = LoadedLlmSerializer(many=True)
    running = serializers.IntegerField()
    waiting = serializers.IntegerField()
    workers = serializers.IntegerField()


class SystemWorkersSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    gpu = serializers.IntegerField()
    agents = serializers.IntegerField()


class SystemConfigurationSerializer(serializers.Serializer):
    debug = serializers.BooleanField()
    maintenance_mode = serializers.BooleanField()
    email = serializers.CharField()
    storage = serializers.ChoiceField(choices=["s3", "local"])
    captcha = serializers.BooleanField()
    toss = serializers.ChoiceField(choices=["off", "test", "live"])
    stripe = serializers.ChoiceField(choices=["off", "test", "live"])


class AdminSystemSerializer(serializers.Serializer):
    checked_at = serializers.FloatField()
    checks = serializers.DictField(child=HealthCheckSerializer())
    gpus = SystemGpuSerializer(many=True)
    stream = SystemStreamSerializer()
    agents = SystemAgentsSerializer()
    workers = SystemWorkersSerializer()
    configuration = SystemConfigurationSerializer()


class ModelStatsSerializer(serializers.Serializer):
    runs = serializers.IntegerField()
    failed = serializers.IntegerField()
    waiting = serializers.IntegerField()


class AdminModelSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    family = serializers.CharField()
    media = serializers.ListField(child=serializers.CharField())
    enabled = serializers.BooleanField()
    weight = serializers.FloatField()
    run_on = serializers.ListField(child=serializers.ChoiceField(choices=["image", "video"]),
                                   help_text="Media types this detector runs on in every job.")
    show_heatmap = serializers.BooleanField(help_text="Users see this detector's heatmap (one image).")
    trial = serializers.BooleanField()
    gpu_mem_mb = serializers.IntegerField()
    queue = serializers.CharField()
    consumers = serializers.IntegerField()
    note = serializers.CharField(allow_blank=True)
    stats_24h = ModelStatsSerializer()
    conda_envs = serializers.ListField(child=serializers.CharField())


class RefundQuoteSerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    amount = serializers.IntegerField()
    credits_to_revoke = serializers.IntegerField()
    reason = serializers.CharField()
    currency = serializers.CharField()


class RefundResultSerializer(serializers.Serializer):
    refund_id = serializers.UUIDField()
    amount = serializers.IntegerField()
    credits_revoked = serializers.IntegerField()
    status = serializers.CharField()


class ApiUsageRowSerializer(serializers.Serializer):
    api_key_id = serializers.UUIDField()
    api_key__name = serializers.CharField()
    api_key__prefix = serializers.CharField()
    api_key__user__email = serializers.EmailField()
    requests = serializers.IntegerField()
    errors = serializers.IntegerField()
    jobs = serializers.IntegerField()
    credits = serializers.IntegerField()


class AdminApiUsageSerializer(serializers.Serializer):
    keys = ApiUsageRowSerializer(many=True)
    active_keys = serializers.IntegerField()


class AdminJobViewSerializer(AdminJobDetailSerializer):
    user_email = serializers.EmailField(allow_null=True)
    tasks_internal = serializers.ListField(child=serializers.DictField())

    class Meta(AdminJobDetailSerializer.Meta):
        fields = [*AdminJobDetailSerializer.Meta.fields, "user_email", "tasks_internal"]


class CreditAdjustResultSerializer(serializers.Serializer):
    balance = serializers.IntegerField()
    applied = serializers.IntegerField(help_text="The change made; a removal is capped at the available balance.")
    entry_id = serializers.UUIDField()


class CountSerializer(serializers.Serializer):
    removed = serializers.IntegerField(required=False)
    revoked = serializers.IntegerField(required=False)


class SetupCheckSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    always = serializers.BooleanField(help_text="Runs on every job and cannot be turned off (metadata / C2PA).")
    enabled = serializers.BooleanField()


class SetupStreamModelSerializer(serializers.Serializer):
    model_id = serializers.CharField()
    name = serializers.CharField()
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    face_crop = serializers.ChoiceField(choices=["always", "optional", "none"],
                                        help_text="Whether the detector can crop to faces before scoring.")
    face_crop_default = serializers.BooleanField()
    face_crop_setting = serializers.BooleanField(allow_null=True, help_text="Admin's choice; null = the default.")


class SetupLongVideoSerializer(serializers.Serializer):
    online = serializers.BooleanField()
    model = serializers.CharField(allow_blank=True, help_text="Empty = the first available detector.")
    models = SetupStreamModelSerializer(many=True)


class DetectionSetupSerializer(serializers.Serializer):
    checks = SetupCheckSerializer(many=True)
    long_video = SetupLongVideoSerializer()


class DetectionSetupUpdateSerializer(serializers.Serializer):
    audit_steps = serializers.ListField(child=serializers.CharField(max_length=32), required=False)
    long_video_model = serializers.CharField(max_length=64, allow_blank=True, required=False)
    long_video_face_crops = serializers.DictField(
        child=serializers.BooleanField(allow_null=True), required=False,
        help_text="{model_id: true|false|null}; null returns the detector to its default.")
