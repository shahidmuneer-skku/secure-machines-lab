"""Celery tasks for orchestration (queue sml.default / sml.results / sml.maintenance)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from sml.queues import STREAM

logger = logging.getLogger(__name__)


@shared_task(name="sml.jobs.dispatch", ignore_result=True)
def dispatch() -> int:
    from .dispatcher import dispatch_pending

    return dispatch_pending()


# A worker's result must not be lost to a transient error (database restart, a deploy whose
# migration ran before this process restarted): retry with backoff for about an hour. Beyond that,
# requeue_stale replays the copy the worker kept in Redis.
@shared_task(name="sml.jobs.record_task_event", ignore_result=True, acks_late=True, autoretry_for=(Exception,),
             retry_backoff=5, retry_backoff_max=600, retry_jitter=True, max_retries=12)
def record_task_event(payload: dict) -> None:
    from .results import record_task_event as _record

    _record(payload)


@shared_task(name="sml.jobs.record_explanation_event", ignore_result=True, acks_late=True)
def record_explanation_event(payload: dict) -> None:
    from .explain import record_explanation_event as _record

    _record(payload)


def replay_kept_results(now: datetime) -> int:
    """Record results the workers delivered but the API never processed (kept in Redis by workers).

    A worker keeps each final result for 24 h. If its task is still open here a minute later, the
    message was lost; replaying it is safe because recording ignores stale or repeated events.
    """
    from django.utils.dateparse import parse_datetime

    from .live import kept_results
    from .models import JobTask
    from .results import record_task_event as _record

    open_tasks = list(JobTask.objects.filter(status__in=[JobTask.Status.RUNNING, JobTask.Status.DISPATCHED])
                      .exclude(queue=STREAM).values_list("pk", "attempt"))
    kept = kept_results([str(pk) for pk, _ in open_tasks])
    count = 0
    for pk, attempt in open_tasks:
        payload = kept.get(str(pk))
        if not payload or int(payload.get("attempt", 0)) != attempt:
            continue
        kept_at = parse_datetime(str(payload.get("kept_at", ""))) or now
        if now - kept_at < timedelta(seconds=60):
            continue  # the message is probably still on its way
        logger.warning("Replaying the kept result of task %s (its message was lost)", pk)
        _record(payload)
        count += 1
    return count


@shared_task(name="sml.maintenance.requeue_stale", ignore_result=True)
def requeue_stale() -> int:
    """Fail RUNNING tasks whose worker stopped heart-beating well past the model timeout, and
    DISPATCHED tasks no worker picked up within STALE_DISPATCH_HOURS."""
    from sml.catalog.registry import registry

    from .live import task_progress
    from .models import JobTask
    from .results import record_task_event as _record

    now = timezone.now()
    reg = registry()
    count = replay_kept_results(now)
    # Streamed long-form scans report through their own channel (sml/jobs/streams.py).
    running = (JobTask.objects.filter(status=JobTask.Status.RUNNING, started_at__lt=now - timedelta(minutes=5))
               .exclude(queue=STREAM))
    live = task_progress([str(t.pk) for t in running])
    for task in running:
        spec = reg.get(task.target)
        timeout = spec.timeout(task.media_type, 600) if spec else 3600
        beat = live.get(str(task.pk), {}).get("updated_at")
        stale_since = task.started_at
        if beat:
            from django.utils.dateparse import parse_datetime

            stale_since = parse_datetime(beat) or stale_since
        if now - stale_since > timedelta(seconds=timeout + 300):
            logger.warning("Reaping stuck task %s", task.pk)
            _record({"event": "finished", "task_id": str(task.pk), "attempt": task.attempt, "status": "failed",
                     "error_code": "WORKER_LOST", "error_message": "The worker stopped responding."})
            count += 1
    # Safety net: a task whose message was lost or dead-lettered would otherwise keep its job
    # (and the user's credit hold) open forever. Late deliveries are ignored once it is failed.
    cutoff = now - timedelta(hours=settings.STALE_DISPATCH_HOURS)
    never_picked = JobTask.objects.filter(status=JobTask.Status.DISPATCHED, dispatched_at__lt=cutoff)
    for task in never_picked.exclude(queue=STREAM):
        logger.warning("Task %s was never picked up; failing it", task.pk)
        _record({"event": "finished", "task_id": str(task.pk), "attempt": task.attempt, "status": "failed",
                 "error_code": "QUEUE_TIMEOUT", "error_message": "No worker picked this task up in time."})
        count += 1
    return count


@shared_task(name="sml.maintenance.expire_credits", ignore_result=True)
def expire_credits() -> int:
    from sml.credits.services import expire_all_due

    return expire_all_due()


@shared_task(name="sml.maintenance.release_stale_holds", ignore_result=True)
def release_stale_holds() -> int:
    from sml.credits.services import release_stale_holds as _release

    return _release()


@shared_task(name="sml.maintenance.expire_streams", ignore_result=True)
def expire_streams() -> int:
    from .streams import expire_stale_sessions

    return expire_stale_sessions()


@shared_task(name="sml.maintenance.audit_ledgers", ignore_result=True)
def audit_ledgers() -> int:
    from sml.credits.services import audit_ledgers as _audit

    return len(_audit())


@shared_task(name="sml.maintenance.purge_expired", ignore_result=True)
def purge_expired() -> int:
    from .retention_tasks import purge_expired as _purge

    return _purge()


@shared_task(name="sml.maintenance.prune_logs", ignore_result=True)
def prune_logs() -> None:
    from sml.apikeys.models import ApiRequestLog
    from sml.core.models import IdempotencyRecord

    ApiRequestLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=30)).delete()
    IdempotencyRecord.objects.filter(created_at__lt=timezone.now() - timedelta(days=2)).delete()
