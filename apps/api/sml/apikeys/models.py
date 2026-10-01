"""Personal API keys for programmatic access.

Format: sml_<env>_<prefix>_<secret>. Only an HMAC-SHA256 of the secret (keyed by
API_KEY_PEPPER) is stored; the full key is shown exactly once at creation.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings
from django.db import models
from django.utils import timezone

from sml.core.models import TimeStampedModel


class Scope(models.TextChoices):
    DETECT_WRITE = "detect:write", "Submit detection jobs"
    JOBS_READ = "jobs:read", "Read jobs and results"
    JOBS_WRITE = "jobs:write", "Cancel, re-run and delete jobs"
    REPORTS_READ = "reports:read", "Generate and download reports"
    CREDITS_READ = "credits:read", "Read credit balance and ledger"
    NEWS_WRITE = "news:write", "Submit news verification cases"
    STUDIO_WRITE = "studio:write", "Generate and edit images in the image studio"


DEFAULT_SCOPES = [Scope.DETECT_WRITE, Scope.JOBS_READ, Scope.REPORTS_READ, Scope.CREDITS_READ]


class ApiKey(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=16, unique=True)
    secret_hash = models.CharField(max_length=64)
    last_four = models.CharField(max_length=4)
    scopes = models.JSONField(default=list)
    allowed_ips = models.JSONField(default=list, blank=True, help_text="CIDR list; empty = any IP.")
    rate_limit_per_minute = models.PositiveIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)
    rotated_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.display_key})"

    @property
    def display_key(self) -> str:
        return f"sml_{settings.API_KEY_ENV_LABEL}_{self.prefix}_…{self.last_four}"

    @property
    def status(self) -> str:
        if self.revoked_at:
            return "revoked"
        if self.expires_at and self.expires_at <= timezone.now():
            return "expired"
        return "active"

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def ip_allowed(self, ip: str | None) -> bool:
        if not self.allowed_ips:
            return True
        if not ip:
            return False
        addr = ipaddress.ip_address(ip)
        return any(addr in ipaddress.ip_network(cidr, strict=False) for cidr in self.allowed_ips)


class ApiKeyUsageDaily(models.Model):
    api_key = models.ForeignKey(ApiKey, on_delete=models.CASCADE, related_name="usage_days")
    date = models.DateField()
    requests = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    jobs_created = models.PositiveIntegerField(default=0)
    credits_spent = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["api_key", "date"], name="uniq_key_usage_day")]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.api_key} {self.date}: {self.requests} requests"


class ApiRequestLog(models.Model):
    """Recent request log per key (kept for 30 days) for the key's usage page."""

    api_key = models.ForeignKey(ApiKey, on_delete=models.CASCADE, related_name="request_logs")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=255)
    status = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["api_key", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.method} {self.path} {self.status}"
