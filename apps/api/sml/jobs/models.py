"""Jobs, their tasks, produced artifacts and a persisted processing timeline.

State machine (Job.status):
    queued → running → succeeded | failed | canceled
    any terminal job → expired (media and artifacts purged by retention)
A job fans out into tasks: one per selected model, one per audit step
(metadata always runs), or one long-video / news / image studio task.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from sml.core.models import TimeStampedModel


class JobBatch(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_batches")
    name = models.CharField(max_length=120, blank=True, default="")
    source = models.CharField(max_length=16, default="web")


class Job(TimeStampedModel):
    class Kind(models.TextChoices):
        DETECT = "detect", "Detection"
        LONG_VIDEO = "long_video", "Long-form video"
        NEWS = "news", "News verification"
        STUDIO = "studio", "Image studio"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"

    class Verdict(models.TextChoices):
        FAKE = "fake", "Likely manipulated / AI-generated"
        REAL = "real", "Likely authentic"
        NO_FACE = "no_face", "No face detected"
        INCONCLUSIVE = "inconclusive", "Inconclusive"

    class Truth(models.TextChoices):
        """What the file really is, as labelled by an administrator; measures detector accuracy."""

        AUTHENTIC = "authentic", "Authentic"
        FACE_SWAP = "face_swap", "Face swap"
        AI_GENERATED = "ai_generated", "AI-generated"

    class Source(models.TextChoices):
        WEB = "web", "Web app"
        API = "api", "API"
        TRIAL = "trial", "Guest trial"

    TERMINAL = {Status.SUCCEEDED, Status.FAILED, Status.CANCELED, Status.EXPIRED}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                             related_name="jobs")
    guest_token = models.CharField(max_length=64, blank=True, default="", db_index=True)
    api_key = models.ForeignKey("apikeys.ApiKey", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="jobs")
    batch = models.ForeignKey(JobBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="jobs")
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.WEB)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.DETECT, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    media = models.ForeignKey("media.MediaObject", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="jobs")
    media_type = models.CharField(max_length=8, blank=True, default="")
    title = models.CharField(max_length=255, blank=True, default="", help_text="File name or case title.")
    models_selected = models.JSONField(default=list)
    audit_steps = models.JSONField(default=list)
    options = models.JSONField(default=dict, blank=True)
    locale = models.CharField(max_length=5, default="en")
    priority = models.PositiveSmallIntegerField(default=4)

    stage = models.CharField(max_length=32, default="queued")
    progress = models.FloatField(default=0.0)
    verdict = models.CharField(max_length=16, choices=Verdict.choices, blank=True, default="")
    fake_probability = models.FloatField(null=True, blank=True)
    verdict_reasons = models.JSONField(default=list, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    partial = models.BooleanField(default=False, help_text="Some models failed but a verdict was produced.")

    credits_quoted = models.PositiveIntegerField(default=0)
    credits_charged = models.PositiveIntegerField(default=0)
    quote_lines = models.JSONField(default=list, blank=True)
    hold = models.ForeignKey("credits.CreditHold", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")

    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    cancel_requested = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    purged_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    run_number = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reruns")
    # Ground truth for measuring detectors (admin only, never shown to the job's owner).
    truth = models.CharField(max_length=16, choices=Truth.choices, blank=True, default="", db_index=True)
    truth_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    truth_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.pk}:{self.status}"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL


class JobTask(TimeStampedModel):
    class Kind(models.TextChoices):
        MODEL = "model", "Model"
        AUDIT = "audit", "Audit step"
        LONG_VIDEO = "long_video", "Long-form video scan"
        NEWS = "news", "News verification"
        STUDIO = "studio", "Image generation / editing"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for a slot"
        DISPATCHED = "dispatched", "In queue"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Done"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        SKIPPED = "skipped", "Skipped"

    TERMINAL = {Status.SUCCEEDED, Status.FAILED, Status.CANCELED, Status.SKIPPED}
    ACTIVE = {Status.DISPATCHED, Status.RUNNING}

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="tasks")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    target = models.CharField(max_length=64, help_text="Model id or audit step id.")
    media_type = models.CharField(max_length=8, blank=True, default="")
    media = models.ForeignKey("media.MediaObject", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+", help_text="Defaults to the job's media.")
    wait_for_models = models.BooleanField(
        default=False, help_text="Dispatch only after the job's model tasks have finished (news verification)."
    )
    queue = models.CharField(max_length=100)
    priority = models.PositiveSmallIntegerField(default=4)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempt = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=2)
    progress = models.FloatField(default=0.0)
    stage_message = models.CharField(max_length=255, blank=True, default="")
    dispatched_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    worker = models.CharField(max_length=128, blank=True, default="")
    gpu = models.CharField(max_length=32, blank=True, default="")
    result = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    error_detail = models.TextField(blank=True, default="", help_text="Technical detail for staff only.")
    fallback_for = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="fallbacks")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "queue", "-priority", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.target}:{self.status}"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL


class Artifact(TimeStampedModel):
    class Kind(models.TextChoices):
        XAI = "xai", "Explainability map"
        FACE = "face", "Face crop"
        VIDEO = "video", "Annotated video"
        FRAMES = "frames", "Per-frame scores"
        REPORT = "report", "Report"
        OTHER = "other", "Other"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="artifacts")
    task = models.ForeignKey(JobTask, null=True, blank=True, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    label = models.CharField(max_length=128, blank=True, default="")
    storage_key = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    size_bytes = models.BigIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)


class JobEvent(models.Model):
    """Processing timeline.

    `message` is the operator's view (detector names, GPUs, errors) shown only in the admin
    console. Users see an event only when it has a `public_message`, which never names the
    detectors or describes how the analysis works.
    """

    class Level(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="events")
    task = models.ForeignKey(JobTask, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    level = models.CharField(max_length=8, choices=Level.choices, default=Level.INFO)
    code = models.CharField(max_length=48)
    message = models.CharField(max_length=500)
    public_message = models.CharField(max_length=500, blank=True, default="")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.code}: {self.message[:60]}"


class Explanation(TimeStampedModel):
    """On-demand "Explain why" reasoning produced by the OpenClaude/Qwen agent."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Done"
        FAILED = "failed", "Failed"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="explanations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    engine = models.CharField(max_length=32)
    model_name = models.CharField(max_length=128)
    locale = models.CharField(max_length=5, default="en")
    content = models.TextField(blank=True, default="")
    progress_log = models.JSONField(default=list, blank=True)
    hold = models.ForeignKey("credits.CreditHold", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    credits_charged = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=500, blank=True, default="")
    error_detail = models.TextField(blank=True, default="", help_text="Technical detail for staff only.")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class StreamSession(TimeStampedModel):
    """A long-form scan whose video is streamed to the stream service and never stored.

    Created (and paid for) before the browser connects; the stream service reports the start,
    live intervals and the end through the internal API, and the job is settled per minute analysed.
    """

    class Status(models.TextChoices):
        CREATED = "created", "Waiting for the upload"
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"
        EXPIRED = "expired", "Expired"

    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="stream")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stream_sessions")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED, db_index=True)
    model_id = models.CharField(max_length=64)
    model_name = models.CharField(max_length=128, blank=True, default="")
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    duration_seconds = models.FloatField(help_text="As reported by the browser; the service probes the file.")
    start_seconds = models.FloatField(default=0.0)
    end_seconds = models.FloatField(null=True, blank=True)
    interval_seconds = models.FloatField()
    whole_video = models.BooleanField(default=False)
    face_crop = models.BooleanField(null=True, blank=True, help_text="Empty = the detector's default.")
    reserved_seconds = models.FloatField()
    analysed_seconds = models.FloatField(default=0.0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)
    # Set when the stream service fetches the scan parameters; a session can be claimed once.
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.model_id}, {self.status})"
