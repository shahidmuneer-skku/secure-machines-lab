from __future__ import annotations

from django.conf import settings
from django.db import models

from sml.core.models import TimeStampedModel


class MediaObject(TimeStampedModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploading"
        READY = "ready", "Ready"
        REJECTED = "rejected", "Rejected"
        DELETED = "deleted", "Deleted"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                              related_name="media")
    guest_token = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADING, db_index=True)
    media_type = models.CharField(max_length=8, choices=MediaType.choices)
    original_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=8)
    content_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    storage_key = models.CharField(max_length=255, unique=True)
    thumbnail_key = models.CharField(max_length=255, blank=True, default="")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    frame_count = models.PositiveIntegerField(null=True, blank=True)
    codec = models.CharField(max_length=32, blank=True, default="")
    s3_multipart_upload_id = models.CharField(max_length=255, blank=True, default="")
    rejection_reason = models.CharField(max_length=255, blank=True, default="")
    training_consent = models.BooleanField(default=False, help_text="Owner had opted in when uploading.")
    # Images made in the image studio: the job that generated or edited them (purged with it).
    generated_by = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="outputs")
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name
