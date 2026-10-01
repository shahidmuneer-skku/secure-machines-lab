"""Cross-cutting models: base classes, platform settings and the audit log."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import models

from .ids import uuid7


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PlatformSettings(models.Model):
    """Singleton with every admin-tunable platform knob.

    Credit prices live in `credits.PriceRule`; this holds everything else so the
    admin panel has one settings form. Read through `PlatformSettings.load()`,
    which is cached and invalidated on save.
    """

    CACHE_KEY = "platform-settings:v1"

    # Guest trial (anonymous homepage detections, images only)
    guest_trial_enabled = models.BooleanField(default=True)
    guest_trial_images_per_day = models.PositiveIntegerField(default=3)
    guest_trial_models = models.JSONField(
        default=list, blank=True,
        help_text="Model variant ids used for guest trials. Empty = the default image set.",
    )

    # What runs on every detection job (users never choose). Detectors per media type are set on
    # Admin → Models (catalog.ModelOverride); the metadata/C2PA check always runs.
    audit_steps = models.JSONField(
        default=list, blank=True, help_text="Extra checks run on every detection job: face, safety, fas.",
    )
    long_video_model = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Stream-service detector for long-form scans. Empty = the first available one.",
    )
    long_video_face_crops = models.JSONField(
        default=dict, blank=True,
        help_text="Per long-form detector: crop to faces before scoring ({model_id: true|false}). "
                  "Missing = the detector's default.",
    )
    # Image studio (owner, 2026-10-01): the model users get for each mode (config/studio.yaml). It stays
    # loaded on the studio GPU; users never choose it.
    studio_enabled = models.BooleanField(default=True)
    studio_generate_model = models.CharField(max_length=64, blank=True, default="qwen-image-2512",
                                             help_text="Studio model for text-to-image. Empty = generation off.")
    studio_edit_model = models.CharField(max_length=64, blank=True, default="qwen-image-edit-2511",
                                         help_text="Studio model for editing reference images. Empty = editing off.")
    exief_weight = models.FloatField(
        default=3.0,
        help_text="Weight of the EXIEF metadata verdict in the AI-generation analysis, relative to one "
                  "detector of weight 1 (confirmed counts as 100% fake, suspect 80%, weak 60%; 0 = off).",
    )

    # Free credits
    signup_bonus_credits = models.PositiveIntegerField(default=50)
    signup_bonus_expiry_days = models.PositiveIntegerField(default=30)
    daily_free_credits = models.PositiveIntegerField(default=10)
    purchased_credit_expiry_days = models.PositiveIntegerField(
        default=365, help_text="0 = purchased credits never expire."
    )

    # Retention (days) for users without a subscription; plans override.
    free_retention_days = models.PositiveIntegerField(default=7)

    # Queue fairness
    free_max_inflight_tasks = models.PositiveIntegerField(default=4)
    api_access_requires_plan = models.BooleanField(
        default=False, help_text="If on, only subscribers whose plan grants API access can use API keys."
    )

    # Reasoning / news engines
    reasoning_engine = models.CharField(
        max_length=32, default="openclaude",
        choices=[("openclaude", "OpenClaude (local Qwen)"), ("ollama", "Ollama direct")],
    )
    reasoning_model = models.CharField(max_length=128, default="qwen3.6:27b")
    news_engine = models.CharField(
        max_length=32, default="openclaude",
        choices=[("openclaude", "OpenClaude (local Qwen)"), ("claude", "Claude (Anthropic API)")],
    )
    news_model = models.CharField(max_length=128, default="qwen3.6:27b")

    # Verdict thresholds
    fake_threshold = models.FloatField(default=0.5)

    # Operations
    maintenance_mode = models.BooleanField(default=False)
    announcement = models.TextField(blank=True, default="")
    signups_enabled = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "platform settings"
        verbose_name_plural = "platform settings"

    def __str__(self) -> str:
        return "Platform settings"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls) -> PlatformSettings:
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 60)
        return obj


class AuditLog(UUIDModel):
    """Append-only record of security-relevant and administrative actions."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_label = models.CharField(max_length=255, blank=True, default="")
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    target_label = models.CharField(max_length=255, blank=True, default="")
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_label} {self.action}"


class IdempotencyRecord(models.Model):
    principal = models.CharField(max_length=128)
    key = models.CharField(max_length=128)
    fingerprint = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["principal", "key"], name="uniq_idempotency_key")]

    def __str__(self) -> str:
        return f"{self.principal} {self.key}"
