"""Job lifecycle: quote → create (reserve credits) → dispatch → finalize; cancel, re-run, delete."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from sml.catalog import access
from sml.catalog.registry import registry
from sml.core.exceptions import ApiError, Conflict, InvalidMedia
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.credits import services as credits
from sml.media.models import MediaObject
from sml.queues import AUDIT_PREFIX, LONG_VIDEO_PREFIX, MODEL_PREFIX

from .models import Job, JobBatch, JobTask
from .retention import priority_for, retention_days_for
from .timeline import emit, push_job_state

logger = logging.getLogger(__name__)

ALWAYS_AUDIT = ["metadata"]


class MaintenanceMode(ApiError):
    status_code = 503
    default_code = "MAINTENANCE"
    default_detail = "The platform is in maintenance mode. Please try again shortly."
    title = "Maintenance"


@dataclass
class JobRequest:
    media: MediaObject
    module: str = "detect"  # detect | long_video
    models: list[str] | None = None
    audit_steps: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    locale: str = "en"


@dataclass
class PreparedJob:
    request: JobRequest
    models: list[str]
    audit_steps: list[str]
    quote: pricing.Quote


def _check_platform() -> None:
    if PlatformSettings.load().maintenance_mode:
        raise MaintenanceMode()


def prepare(user: Any, req: JobRequest, *, api_key: Any = None) -> PreparedJob:
    """Validate access and price a request without side effects (used by /jobs/quote)."""
    media = req.media
    if media.status != MediaObject.Status.READY:
        raise InvalidMedia("The upload is not ready (still uploading, rejected or deleted).")
    if req.module == "long_video":
        if media.media_type != "video":
            raise InvalidMedia("Long-form scanning needs a video.")
        access.assert_module_allowed(user, "long_video")
        reg = registry()
        chosen = [m for m in (req.models or []) if m in reg.long_video_models] or [
            m.id for m in reg.long_video_models.values() if m.default_selected
        ][:1]
        if not chosen:
            raise ApiError("No long-form video model is configured.")
        return PreparedJob(req, chosen[:1], [], pricing.quote_long_video(media.duration_seconds or 0))

    access.assert_module_allowed(user, "detect")
    models = access.resolve_models(user, media.media_type, req.models, api_key)
    allowed_steps = set(access.allowed_audit_steps(user))
    steps = [s for s in req.audit_steps if s in registry().audit_steps and s not in ALWAYS_AUDIT]
    denied = [s for s in steps if s not in allowed_steps]
    if denied:
        raise ApiError(f"Audit steps not permitted: {', '.join(denied)}", extra={"audit_steps": denied})
    quote = pricing.quote_media(media.media_type, media.duration_seconds, "detect")
    return PreparedJob(req, models, ALWAYS_AUDIT + steps, quote)


def _task_specs(prepared: PreparedJob) -> list[tuple[str, str, str]]:
    """(kind, target, queue) for every task a job needs."""
    media_type = prepared.request.media.media_type
    if prepared.request.module == "long_video":
        return [(JobTask.Kind.LONG_VIDEO, prepared.models[0], LONG_VIDEO_PREFIX + prepared.models[0])]
    specs = [(JobTask.Kind.AUDIT, s, AUDIT_PREFIX + s) for s in prepared.audit_steps]
    specs += [(JobTask.Kind.MODEL, m, MODEL_PREFIX + m) for m in prepared.models]
    del media_type
    return specs


def _create_job(user: Any, prepared: PreparedJob, *, source: str, api_key: Any = None,
                batch: JobBatch | None = None, guest_token: str = "", parent: Job | None = None) -> Job:
    req = prepared.request
    media = req.media
    priority = priority_for(user, source)
    kind = Job.Kind.LONG_VIDEO if req.module == "long_video" else Job.Kind.DETECT
    job = Job.objects.create(
        user=user, guest_token=guest_token, api_key=api_key if hasattr(api_key, "prefix") else None,
        batch=batch, source=source, kind=kind, media=media, media_type=media.media_type,
        title=media.original_name, models_selected=prepared.models, audit_steps=prepared.audit_steps,
        options=req.options, locale=req.locale, priority=priority, credits_quoted=prepared.quote.credits,
        quote_lines=[{"label": ln.label, "credits": ln.credits} for ln in prepared.quote.lines],
        expires_at=timezone.now() + timedelta(days=retention_days_for(user)),
        run_number=(parent.run_number + 1) if parent else 1, parent=parent,
    )
    if user is not None:
        hold = credits.reserve(user, prepared.quote.credits, reference_type="job", reference_id=str(job.pk))
        job.hold = hold
        job.save(update_fields=["hold"])
    reg = registry()
    for kind_, target, queue in _task_specs(prepared):
        max_attempts = 2 if kind_ == JobTask.Kind.MODEL else 1
        JobTask.objects.create(job=job, kind=kind_, target=target, media_type=media.media_type, queue=queue,
                               priority=priority, max_attempts=max_attempts)
    names = ", ".join(reg.get(m).name(req.locale) if reg.get(m) else m for m in prepared.models)
    emit(job, "job.created", f"Job created for {media.original_name}", data={"models": prepared.models})
    if user is not None and prepared.quote.credits:
        emit(job, "credits.reserved", f"{prepared.quote.credits} credits reserved", data={
            "credits": prepared.quote.credits})
    emit(job, "job.queued", f"Queued: {names or 'analysis'}", data={"priority": priority})
    push_job_state(job)
    return job


def _after_commit_dispatch() -> None:
    from .tasks import dispatch

    transaction.on_commit(lambda: dispatch.delay())


def create_job(user: Any, req: JobRequest, *, source: str = "web", api_key: Any = None,
               guest_token: str = "") -> Job:
    _check_platform()
    prepared = prepare(user, req, api_key=api_key)
    with transaction.atomic():
        job = _create_job(user, prepared, source=source, api_key=api_key, guest_token=guest_token)
        _after_commit_dispatch()
    if api_key is not None and hasattr(api_key, "prefix"):
        from sml.apikeys.services import bump_usage

        bump_usage(api_key, jobs=1, credits=prepared.quote.credits)
    return job


def create_batch(user: Any, reqs: list[JobRequest], *, source: str = "web", api_key: Any = None,
                 name: str = "") -> tuple[JobBatch, list[Job]]:
    """All-or-nothing: if any job can't be created (e.g. credits run out) nothing is created."""
    _check_platform()
    prepared = [prepare(user, r, api_key=api_key) for r in reqs]
    total = sum(p.quote.credits for p in prepared)
    with transaction.atomic():
        batch = JobBatch.objects.create(user=user, name=name[:120], source=source)
        jobs = [_create_job(user, p, source=source, api_key=api_key, batch=batch) for p in prepared]
        _after_commit_dispatch()
    if api_key is not None and hasattr(api_key, "prefix"):
        from sml.apikeys.services import bump_usage

        bump_usage(api_key, jobs=len(jobs), credits=total)
    return batch, jobs


def cancel_job(job: Job, *, actor: Any = None) -> Job:
    """Queued work is canceled at once (credits released); running work is stopped best-effort."""
    from .live import request_cancel
    from .results import finalize_job

    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job.pk)
        if job.is_terminal:
            raise Conflict("This job has already finished.")
        job.cancel_requested = True
        job.save(update_fields=["cancel_requested", "updated_at"])
        now = timezone.now()
        pending = job.tasks.filter(status__in=[JobTask.Status.PENDING, JobTask.Status.DISPATCHED])
        pending.update(status=JobTask.Status.CANCELED, finished_at=now, stage_message="Canceled")
        emit(job, "job.cancel_requested", "Cancellation requested", level="warning")
        running = job.tasks.filter(status=JobTask.Status.RUNNING).exists()
        if running:
            transaction.on_commit(lambda: request_cancel(str(job.pk)))
        else:
            finalize_job(job)
    job.refresh_from_db()
    return job


def rerun_job(job: Job, *, user: Any, source: str = "web", api_key: Any = None) -> Job:
    if not job.is_terminal or job.status == Job.Status.EXPIRED or job.media is None:
        raise Conflict("Only finished jobs whose media is still retained can be re-run.")
    req = JobRequest(
        media=job.media, module="long_video" if job.kind == Job.Kind.LONG_VIDEO else "detect",
        models=job.models_selected, audit_steps=[s for s in job.audit_steps if s not in ALWAYS_AUDIT],
        options=job.options, locale=job.locale,
    )
    _check_platform()
    prepared = prepare(user, req, api_key=api_key)
    with transaction.atomic():
        new = _create_job(user, prepared, source=source, api_key=api_key, parent=job)
        _after_commit_dispatch()
    return new


def delete_job(job: Job) -> None:
    """Hide the job and purge its media/artifacts now; the row stays for billing history."""
    from .retention_tasks import purge_job_files

    if not job.is_terminal:
        cancel_job(job)
    job.deleted_at = timezone.now()
    job.save(update_fields=["deleted_at", "updated_at"])
    purge_job_files(job)
