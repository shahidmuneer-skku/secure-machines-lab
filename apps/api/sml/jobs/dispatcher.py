"""Fair dispatch of pending tasks into RabbitMQ.

Tasks wait in PostgreSQL as PENDING (this doubles as the transactional outbox).
The dispatcher releases them into model queues highest-priority first, but never
lets one principal hold more than its in-flight cap, so a user submitting 500
files cannot starve everyone else. It runs after every job creation / task
completion and every 5 s from Celery beat.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from sml.catalog.registry import registry
from sml.queues import WORKER_TASK

from .models import Job, JobTask
from .retention import max_inflight_for
from .timeline import emit

logger = logging.getLogger(__name__)

DISPATCH_LOCK_ID = 7_412_001
BATCH_LIMIT = 500


def _principal(job: Job) -> str:
    return f"u:{job.user_id}" if job.user_id else f"g:{job.guest_token}"


def _try_lock() -> bool:
    if connection.vendor != "postgresql":
        return True
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [DISPATCH_LOCK_ID])
        return bool(cur.fetchone()[0])


def envelope(task: JobTask) -> dict[str, Any]:
    job = task.job
    media = task.media or job.media
    return {
        "v": 1,
        "task_id": str(task.pk),
        "job_id": str(job.pk),
        "user_id": str(job.user_id) if job.user_id else None,
        "attempt": task.attempt,
        "kind": task.kind,
        "target": task.target,
        "media_type": task.media_type,
        "media": {
            "storage_key": media.storage_key,
            "extension": media.extension,
            "original_name": media.original_name,
            "sha256": media.sha256,
            "duration_seconds": media.duration_seconds,
        } if media else None,
        "options": job.options,
        "locale": job.locale,
        "family_hint": job.options.get("family_hint", ""),
        "news_case_id": job.options.get("news_case_id"),
        "dispatched_at": timezone.now().isoformat(),
        "forensics": _forensics(job) if task.kind == JobTask.Kind.NEWS else None,
        "news_case": _news_case(job) if task.kind == JobTask.Kind.NEWS else None,
        "studio": _studio(job) if task.kind == JobTask.Kind.STUDIO else None,
    }


def _studio(job: Job) -> dict[str, Any]:
    """The studio request: the validated parameters, the reference files and the prompt-check model."""
    from sml.core.models import PlatformSettings
    from sml.media.models import MediaObject

    params = dict(job.options.get("studio") or {})
    ids = params.pop("references", [])
    found = {str(m.pk): m for m in MediaObject.objects.filter(pk__in=ids)}
    params["references"] = [{"storage_key": found[i].storage_key, "extension": found[i].extension}
                            for i in ids if i in found]
    params["consent"] = bool((job.options.get("consent") or {}).get("confirmed"))
    params["safety_model"] = PlatformSettings.load().reasoning_model
    return params


def _news_case(job: Job) -> dict[str, Any] | None:
    case = getattr(job, "news_case", None)
    if case is None:
        return None
    return {"input": case.as_input(),
            "media": [{"storage_key": m.storage_key, "extension": m.extension, "media_type": m.media_type,
                       "original_name": m.original_name} for m in case.media.all()]}


def _forensics(job: Job) -> list[dict[str, Any]]:
    """Per attached file, the result of each analysis (face swap, AI generation), handed to
    the news agent as one input. The agent's report is shown to the user, so it is never told which
    detectors ran or how many."""
    from sml.core.models import PlatformSettings

    from .public import ANALYSIS_IDS
    from .results import group_results

    threshold = PlatformSettings.load().fake_threshold
    reg = registry()
    by_file: dict[str, list[JobTask]] = {}
    for t in job.tasks.filter(kind=JobTask.Kind.MODEL).select_related("media"):
        by_file.setdefault(str(t.media_id or job.media_id or ""), []).append(t)
    out = []
    for tasks in by_file.values():
        media = tasks[0].media or job.media
        xai = [a.storage_key for t in tasks for a in t.artifacts.filter(kind="xai", content_type__startswith="image/")]
        out.append({"file": media.original_name if media else "",
                    "analyses": [{"analysis": ANALYSIS_IDS[g["group"]], "status": g["status"],
                                  "fake_prob": g["fake_probability"]}
                                 for g in group_results(tasks, threshold, reg)],
                    "xai_keys": xai[:2]})
    return out


def _publish(tasks: list[JobTask]) -> None:
    from sml.celery import app

    failed: list[str] = []
    for task in tasks:
        try:
            app.send_task(WORKER_TASK, args=[envelope(task)], queue=task.queue, routing_key=task.queue,
                          priority=task.priority)
        except Exception:  # broker errors: put the task back
            logger.exception("Failed to publish task %s", task.pk)
            failed.append(str(task.pk))
    if failed:
        JobTask.objects.filter(pk__in=failed, status=JobTask.Status.DISPATCHED).update(
            status=JobTask.Status.PENDING, dispatched_at=None)


def dispatch_pending() -> int:
    with transaction.atomic():
        if not _try_lock():
            return 0
        blocked_jobs = (JobTask.objects.filter(kind=JobTask.Kind.MODEL)
                        .exclude(status__in=list(JobTask.TERMINAL)).values("job_id"))
        candidates = list(
            JobTask.objects.select_for_update(skip_locked=True, of=("self",))
            .filter(status=JobTask.Status.PENDING, job__cancel_requested=False)
            .exclude(wait_for_models=True, job_id__in=blocked_jobs)
            .select_related("job", "job__media", "job__user", "media")
            .order_by("-priority", "created_at")[:BATCH_LIMIT]
        )
        if not candidates:
            return 0
        inflight: Counter[str] = Counter()
        active = (JobTask.objects.filter(status__in=JobTask.ACTIVE)
                  .values("job__user_id", "job__guest_token").annotate(n=Count("id")))
        for row in active:
            key = f"u:{row['job__user_id']}" if row["job__user_id"] else f"g:{row['job__guest_token']}"
            inflight[key] += row["n"]
        caps: dict[str, int] = {}
        now = timezone.now()
        selected: list[JobTask] = []
        for task in candidates:
            key = _principal(task.job)
            if key not in caps:
                caps[key] = max_inflight_for(task.job.user)
            if inflight[key] >= caps[key]:
                continue
            inflight[key] += 1
            task.status = JobTask.Status.DISPATCHED
            task.dispatched_at = now
            task.attempt += 1
            task.stage_message = "Waiting in queue"
            selected.append(task)
        if not selected:
            return 0
        JobTask.objects.bulk_update(selected, ["status", "dispatched_at", "attempt", "stage_message"])
        for task in selected:
            label = "attempt " + str(task.attempt) if task.attempt > 1 else task.queue
            emit(task.job, "task.dispatched", f"{task.get_kind_display()} '{task.target}' sent to queue ({label})",
                 task=task)
        transaction.on_commit(lambda: _publish(selected))
    return len(selected)
