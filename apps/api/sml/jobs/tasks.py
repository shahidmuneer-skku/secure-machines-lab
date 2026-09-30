"""Celery tasks for orchestration (queue sml.default / sml.results / sml.maintenance)."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="sml.jobs.dispatch", ignore_result=True)
def dispatch() -> int:
    from .dispatcher import dispatch_pending

    return dispatch_pending()


@shared_task(name="sml.jobs.record_task_event", ignore_result=True, acks_late=True)
def record_task_event(payload: dict) -> None:
    from .results import record_task_event as _record

    _record(payload)


@shared_task(name="sml.jobs.record_explanation_event", ignore_result=True, acks_late=True)
def record_explanation_event(payload: dict) -> None:
    from .explain import record_explanation_event as _record

    _record(payload)


@shared_task(name="sml.maintenance.requeue_stale", ignore_result=True)
def requeue_stale() -> int:
    """Fail RUNNING tasks whose worker stopped heart-beating well past the model timeout."""
    from sml.catalog.registry import registry

    from .live import task_progress
    from .models import JobTask
    from .results import record_task_event as _record

    now = timezone.now()
    reg = registry()
    count = 0
    running = JobTask.objects.filter(status=JobTask.Status.RUNNING, started_at__lt=now - timedelta(minutes=5))
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
    return count


@shared_task(name="sml.maintenance.expire_credits", ignore_result=True)
def expire_credits() -> int:
    from sml.credits.services import expire_all_due

    return expire_all_due()


@shared_task(name="sml.maintenance.release_stale_holds", ignore_result=True)
def release_stale_holds() -> int:
    from sml.credits.services import release_stale_holds as _release

    return _release()


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
