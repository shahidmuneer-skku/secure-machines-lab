"""Media/artifact purging for deleted and expired jobs."""

from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

from sml.media import services as media_services
from sml.media import storage
from sml.media.models import MediaObject

from .models import Job

logger = logging.getLogger(__name__)


def purge_job_files(job: Job) -> None:
    for art in job.artifacts.all():
        try:
            storage.delete(art.storage_key)
        except Exception:
            logger.warning("Could not delete artifact %s", art.storage_key, exc_info=True)
    job.artifacts.all().delete()
    files = [job.media] if job.media is not None else []
    if job.kind == Job.Kind.STUDIO:
        # The images it made and every reference image, not only the first (job.media).
        refs = (job.options.get("studio") or {}).get("references") or []
        files += list(MediaObject.objects.filter(pk__in=refs).exclude(pk=job.media_id))
        files += list(job.outputs.all())
    for media in files:
        if media.status != MediaObject.Status.DELETED and not _in_use(media, job):
            media_services.purge(media)
    job.purged_at = timezone.now()
    job.save(update_fields=["purged_at", "updated_at"])


def _in_use(media: MediaObject, job: Job) -> bool:
    """Another job that is not purged yet analyses this file, edits it, or made it."""
    live = Job.objects.filter(deleted_at__isnull=True, purged_at__isnull=True).exclude(pk=job.pk)
    if live.filter(media=media).exists():
        return True
    if media.generated_by_id and media.generated_by_id != job.pk and live.filter(pk=media.generated_by_id).exists():
        return True
    return live.filter(kind=Job.Kind.STUDIO, options__studio__references__contains=[str(media.pk)]).exists()


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
