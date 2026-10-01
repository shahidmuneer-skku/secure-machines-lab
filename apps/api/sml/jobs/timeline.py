"""Writes timeline events and pushes them to live subscribers.

Every event keeps the operator's message (detector names, GPUs, error codes) for the admin
console. Users only ever receive events that carry a `public` message, and only data keys that
say nothing about how the analysis works (credits, verdict, probability).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from sml.core.events import publish_job

from .models import Job, JobEvent, JobTask

PUBLIC_DATA_KEYS = {"credits", "credits_charged", "verdict", "fake_probability", "range_seconds"}


def public_data(data: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (data or {}).items() if k in PUBLIC_DATA_KEYS}


def emit(job: Job, code: str, message: str, *, public: str = "", level: str = JobEvent.Level.INFO,
         task: JobTask | None = None, data: dict[str, Any] | None = None) -> JobEvent:
    event = JobEvent.objects.create(job=job, task=task, level=level, code=code, message=message[:500],
                                    public_message=public[:500], data=data or {})
    if event.public_message:
        payload = {"job_id": str(job.pk), "code": code, "level": level, "message": event.public_message,
                   "data": public_data(event.data), "at": event.created_at.isoformat()}
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
