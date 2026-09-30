"""Media/artifact purging for deleted and expired jobs."""

from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

from sml.media import services as media_services
from sml.media import storage

from .models import Job

logger = logging.getLogger(__name__)


def purge_job_files(job: Job) -> None:
    for art in job.artifacts.all():
        try:
            storage.delete(art.storage_key)
        except Exception:  # noqa: BLE001
            logger.warning("Could not delete artifact %s", art.storage_key, exc_info=True)
    job.artifacts.all().delete()
    media = job.media
    if media is not None and not media.jobs.filter(deleted_at__isnull=True, purged_at__isnull=True).exclude(
            pk=job.pk).exists():
        media_services.purge(media)
    job.purged_at = timezone.now()
    job.save(update_fields=["purged_at", "updated_at"])


def purge_expired(limit: int = 500) -> int:
    now = timezone.now()
    jobs = (Job.objects.filter(expires_at__lte=now, purged_at__isnull=True)
            .filter(Q(status__in=list(Job.TERMINAL)))[:limit])
    count = 0
    for job in jobs:
        purge_job_files(job)
        if job.status != Job.Status.EXPIRED:
            Job.objects.filter(pk=job.pk).update(status=Job.Status.EXPIRED)
        count += 1
    return count
