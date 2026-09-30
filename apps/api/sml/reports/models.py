from django.conf import settings
from django.db import models

from sml.core.models import TimeStampedModel


class Report(TimeStampedModel):
    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        HWP = "hwp", "HWP (Hangul)"
        CSV = "csv", "CSV"
        ZIP = "zip", "ZIP bundle"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Generating"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="reports")
    format = models.CharField(max_length=8, choices=Format.choices)
    locale = models.CharField(max_length=5, default="en")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    run_number = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    storage_key = models.CharField(max_length=255, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    error_message = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    @property
    def filename(self) -> str:
        stem = (self.job.title.rsplit(".", 1)[0] or "report")[:60]
        return f"SML-report_{stem}_v{self.version}_{self.locale}.{self.format}"
