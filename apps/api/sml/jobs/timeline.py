"""Writes timeline events and pushes them to live subscribers."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from sml.core.events import publish_job

from .models import Job, JobEvent, JobTask


def emit(job: Job, code: str, message: str, *, level: str = JobEvent.Level.INFO,
         task: JobTask | None = None, data: dict[str, Any] | None = None) -> JobEvent:
    event = JobEvent.objects.create(job=job, task=task, level=level, code=code, message=message[:500],
                                    data=data or {})
    payload = {
        "job_id": str(job.pk), "task_id": str(task.pk) if task else None, "code": code, "level": level,
        "message": event.message, "data": event.data, "at": event.created_at.isoformat(),
    }
    transaction.on_commit(lambda: publish_job(job, "job.event", payload))
    return event


def push_job_state(job: Job) -> None:
    """Broadcast the job's current summary (status, stage, progress, verdict)."""
    payload = {
        "job_id": str(job.pk), "status": job.status, "stage": job.stage, "progress": round(job.progress, 1),
        "verdict": job.verdict, "fake_probability": job.fake_probability,
        "credits_charged": job.credits_charged,
    }
    transaction.on_commit(lambda: publish_job(job, "job.updated", payload))
