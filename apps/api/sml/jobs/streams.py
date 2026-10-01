"""Long-form scans streamed to the stream service (apps/stream), without storing the video.

Flow: the browser asks for a session (credits for the selected range are reserved and a signed
token is issued) → it streams the file to the stream service over a WebSocket → the service
reports `started`, live `intervals` and `finished` to the internal endpoint → the job is settled
per started minute actually analysed (owner decision 2026-09-30). The job appears in history like
any other; only a preview frame is kept.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from sml.catalog import access
from sml.catalog.registry import registry
from sml.core.events import publish_job
from sml.core.exceptions import ApiError, Conflict
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.credits import services as credits
from sml.media import storage
from sml.queues import STREAM

from . import live
from .errors import user_message
from .models import Artifact, Job, JobTask, StreamSession
from .retention import priority_for, retention_days_for
from .timeline import emit, push_job_state

logger = logging.getLogger(__name__)

MODELS_CACHE_KEY = "stream:models:v1"
RANGE_TOLERANCE = 1.0  # seconds; container durations differ slightly between browser and decoder


class StreamServiceUnavailable(ApiError):
    status_code = 503
    default_code = "STREAM_UNAVAILABLE"
    default_detail = "Long-form scanning is temporarily unavailable. Please try again shortly."
    title = "Service unavailable"


# --- tokens (same format as apps/stream/sml_stream/tokens.py) ---------------------------------

def sign_token(claims: dict[str, Any]) -> str:
    secret = settings.STREAM_SHARED_SECRET
    if not secret:
        raise StreamServiceUnavailable("Long-form streaming is not configured (STREAM_SHARED_SECRET).")
    body = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    body_text = body.rstrip(b"=").decode()
    mac = hmac.new(secret.encode(), body_text.encode(), hashlib.sha256).hexdigest()
    return f"{body_text}.{mac}"


def verify_service_key(presented: str | None) -> bool:
    secret = settings.STREAM_SHARED_SECRET
    return bool(secret and presented and hmac.compare_digest(secret, presented))


# --- catalog -------------------------------------------------------------------------------

def available_models(*, use_cache: bool = True) -> list[dict[str, Any]]:
    """Detectors the stream service can run right now (checkpoints and conda envs present)."""
    if use_cache and (cached := cache.get(MODELS_CACHE_KEY)) is not None:
        return cached
    try:
        resp = httpx.get(f"{settings.STREAM_INTERNAL_URL}/stream/models", timeout=5)
        resp.raise_for_status()
        models = [m for m in resp.json().get("models", []) if isinstance(m, dict) and m.get("model_id")]
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Stream service unavailable: %s", exc)
        raise StreamServiceUnavailable() from exc
    cache.set(MODELS_CACHE_KEY, models, 30)
    return models


# --- sessions ---------------------------------------------------------------------------------

def configured_model() -> dict[str, Any]:
    """The detector the admin chose for long-form scans (Admin → Models), if the service can run it.

    Empty setting = the first available detector. Users never choose and never see which one runs.
    """
    chosen = PlatformSettings.load().long_video_model
    models = available_models()
    model = next((m for m in models if m["model_id"] == chosen), None) if chosen else next(
        (m for m in models if m.get("available")), None)
    if model is None or not model.get("available"):
        logger.warning("Long-form model %r unavailable: %s", chosen or "(first available)",
                       (model or {}).get("reason", "not offered by the stream service"))
        raise ApiError("Long-form scanning is not available right now. Please try again later.")
    return model


@dataclass
class StreamRequest:
    file_name: str
    file_size: int
    duration_seconds: float
    start_seconds: float = 0.0
    end_seconds: float | None = None
    interval_seconds: float = 5.0
    whole_video: bool = False
    locale: str = "en"


def range_seconds(req: StreamRequest) -> float:
    end = req.end_seconds if req.end_seconds is not None else req.duration_seconds
    return max(0.0, min(end, req.duration_seconds) - req.start_seconds)


def quote(req: StreamRequest) -> pricing.Quote:
    return pricing.quote_long_video(range_seconds(req))


def _validate(req: StreamRequest) -> dict[str, Any]:
    model = configured_model()
    if not 0 < req.file_size <= settings.UPLOAD_MAX_VIDEO_BYTES:
        raise ApiError(f"Videos up to {settings.UPLOAD_MAX_VIDEO_BYTES // 1024**3} GB are supported.")
    if not 0 < req.duration_seconds <= settings.UPLOAD_MAX_VIDEO_SECONDS:
        raise ApiError(f"Videos up to {settings.UPLOAD_MAX_VIDEO_SECONDS // 3600} hours are supported.")
    if req.start_seconds < 0 or req.start_seconds >= req.duration_seconds:
        raise ApiError("The start time must be inside the video.")
    if req.end_seconds is not None and not req.start_seconds < req.end_seconds <= req.duration_seconds + 1:
        raise ApiError("The end time must be after the start time and inside the video.")
    if not req.whole_video and not 0.5 <= req.interval_seconds <= 3600:
        raise ApiError("The interval must be between 0.5 seconds and one hour.")
    return model


def create_session(user: Any, req: StreamRequest) -> tuple[StreamSession, str]:
    """Reserve credits for the selected range, create the job and return a signed stream token."""
    from .services import MaintenanceMode

    if PlatformSettings.load().maintenance_mode:
        raise MaintenanceMode()
    access.assert_module_allowed(user, "long_video")
    model = _validate(req)
    model_id = str(model["model_id"])
    face_crop = (PlatformSettings.load().long_video_face_crops or {}).get(model_id)  # None = detector default
    q = quote(req)
    seconds = range_seconds(req)
    now = timezone.now()
    with transaction.atomic():
        job = Job.objects.create(
            user=user, source=Job.Source.WEB, kind=Job.Kind.LONG_VIDEO, media=None, media_type="video",
            title=req.file_name[:255], models_selected=[model_id], audit_steps=[], locale=req.locale,
            priority=priority_for(user, "web"), credits_quoted=q.credits,
            quote_lines=[{"label": ln.label, "credits": ln.credits} for ln in q.lines],
            options={"stream": True, "interval_seconds": req.interval_seconds, "start_sec": req.start_seconds,
                     "end_sec": req.end_seconds, "whole_video": req.whole_video},
            expires_at=now + timedelta(days=retention_days_for(user)),
        )
        job.hold = credits.reserve(user, q.credits, reference_type="job", reference_id=str(job.pk))
        job.save(update_fields=["hold"])
        task = JobTask.objects.create(
            job=job, kind=JobTask.Kind.LONG_VIDEO, target=model_id, media_type="video", queue=STREAM,
            status=JobTask.Status.DISPATCHED, attempt=1, max_attempts=1, priority=job.priority,
            dispatched_at=now, stage_message="Waiting for the video",
        )
        session = StreamSession.objects.create(
            job=job, user=user, model_id=model_id, model_name=str(model.get("name") or model_id)[:128],
            file_name=req.file_name[:255], file_size=req.file_size, duration_seconds=req.duration_seconds,
            start_seconds=req.start_seconds, end_seconds=req.end_seconds, interval_seconds=req.interval_seconds,
            whole_video=req.whole_video, face_crop=face_crop, reserved_seconds=seconds,
        )
        emit(job, "job.created", f"Long-form scan of {req.file_name} with {session.model_name}",
             public=f"Long-form scan requested for {req.file_name}",
             data={"models": [model_id], "range_seconds": round(seconds, 1)})
        if q.credits:
            message = f"{q.credits} credits reserved for {math.ceil(seconds / 60)} min"
            emit(job, "credits.reserved", message, public=message, data={"credits": q.credits})
        message = "Waiting for the video to be streamed"
        emit(job, "job.queued", message, public=message, task=task)
        push_job_state(job)
    # The browser holds this token: it names the session only. The stream service claims the
    # scan's parameters (detector, range, size) from the API, so they never reach the client.
    token = sign_token({"sid": str(session.pk), "exp": int(time.time()) + settings.STREAM_TOKEN_TTL_SECONDS})
    return session, token


def _family(model_id: str) -> str:
    spec = registry().get(model_id)
    return spec.family if spec else "general"


def claim_session(session_id: str) -> dict[str, Any]:
    """Called once by the stream service when the browser authenticates: what was paid for."""
    with transaction.atomic():
        session = StreamSession.objects.select_for_update().filter(pk=session_id).first()
        if session is None:
            raise ApiError("Unknown stream session.", extra={"session_id": session_id})
        if session.claimed_at is not None or session.status != StreamSession.Status.CREATED:
            raise Conflict("This scan token has already been used.")
        if Job.objects.filter(pk=session.job_id, cancel_requested=True).exists():
            raise Conflict("The scan was canceled.")
        session.claimed_at = timezone.now()
        session.save(update_fields=["claimed_at", "updated_at"])
    return {
        "sid": str(session.pk), "model": session.model_id, "name": session.file_name, "size": session.file_size,
        "start": session.start_seconds, "end": session.end_seconds, "max_seconds": session.reserved_seconds,
        "interval": session.interval_seconds, "whole": session.whole_video, "face_crop": session.face_crop,
    }


# --- events from the stream service ------------------------------------------------------------

def _interval(row: dict[str, Any]) -> dict[str, Any]:
    return {"index": int(row.get("index") or 0), "start_sec": float(row.get("start_sec") or 0.0),
            "end_sec": float(row.get("end_sec") or 0.0),
            "fake_prob": max(0.0, min(1.0, float(row.get("fake_probability", row.get("fake_prob")) or 0.0))),
            "frames_used": int(row.get("frames_used") or 0)}


def _analysed(intervals: list[dict[str, Any]]) -> float:
    return sum(max(0.0, i["end_sec"] - i["start_sec"]) for i in intervals)


def handle_event(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event")
    with transaction.atomic():
        session = StreamSession.objects.select_for_update().select_related("job").filter(pk=session_id).first()
        if session is None:
            raise ApiError("Unknown stream session.", extra={"session_id": session_id})
        job = Job.objects.select_for_update().get(pk=session.job_id)
        task = job.tasks.select_for_update().get(queue=STREAM)
        if session.status in (StreamSession.Status.FINISHED, StreamSession.Status.EXPIRED) or (
                job.is_terminal and event != "finished"):
            raise Conflict("This scan has already ended.")
        session.last_event_at = timezone.now()
        if job.is_terminal:
            # Canceled from the job page before the stream began: the job is already settled.
            session.status, session.finished_at = StreamSession.Status.FINISHED, session.last_event_at
            session.save(update_fields=["status", "finished_at", "last_event_at", "updated_at"])
            return {"ok": True, "job_id": str(job.pk), "credits_charged": job.credits_charged, "verdict": job.verdict}
        if event == "started":
            return _on_started(session, job, task, payload)
        if event == "intervals":
            if job.cancel_requested:
                raise Conflict("The scan was canceled.")
            return _on_intervals(session, job, task, payload)
        if event == "finished":
            return _on_finished(session, job, task, payload)
    raise ApiError(f"Unknown stream event {event!r}.")


def _on_started(session: StreamSession, job: Job, task: JobTask, payload: dict[str, Any]) -> dict[str, Any]:
    now = timezone.now()
    session.status = StreamSession.Status.RUNNING
    session.started_at = now
    session.save(update_fields=["status", "started_at", "last_event_at", "updated_at"])
    task.status = JobTask.Status.RUNNING
    task.started_at = now
    task.worker = "stream"
    task.stage_message = "Analysing"
    task.result = {"intervals": [], "duration": payload.get("duration"), "width": payload.get("width"),
                   "height": payload.get("height"), "fps": payload.get("fps"),
                   "range": [payload.get("start_sec"), payload.get("end_sec")]}
    task.save()
    job.status = Job.Status.RUNNING
    job.started_at = now
    job.stage = "analyzing"
    job.save(update_fields=["status", "started_at", "stage", "updated_at"])
    preview = payload.get("preview_jpeg") or ""
    if preview:
        try:
            data = base64.b64decode(preview, validate=True)
            key = f"jobs/{job.pk}/{task.pk}/preview.jpg"
            storage.save_bytes(key, data)
            Artifact.objects.create(job=job, task=task, kind=Artifact.Kind.OTHER, label="Preview", storage_key=key,
                                    content_type="image/jpeg", size_bytes=len(data), meta={"preview": True})
        except (binascii.Error, ValueError, OSError):
            logger.warning("Stream %s: preview frame not stored", session.pk, exc_info=True)
    emit(job, "task.started", f"{session.model_name} started on the stream service", task=task,
         public="Analysing the video")
    live.record_progress(str(task.pk), 1, "Video received; analysing", log=True)
    push_job_state(job)
    return {"ok": True}


def _on_intervals(session: StreamSession, job: Job, task: JobTask, payload: dict[str, Any]) -> dict[str, Any]:
    rows = [_interval(r) for r in payload.get("intervals") or []]
    known = {i["index"]: i for i in (task.result or {}).get("intervals", [])}
    for row in rows:
        known[row["index"]] = row
    intervals = sorted(known.values(), key=lambda i: i["index"])
    total = int(payload.get("total") or 0)
    progress = min(99.0, 100.0 * len(intervals) / total) if total else min(95.0, float(len(intervals)))
    task.result = {**(task.result or {}), "intervals": intervals}
    task.progress = progress
    task.save(update_fields=["result", "progress", "updated_at"])
    job.progress = progress
    job.save(update_fields=["progress", "updated_at"])
    session.analysed_seconds = _analysed(intervals)
    session.save(update_fields=["analysed_seconds", "last_event_at", "updated_at"])
    if rows:
        last = rows[-1]
        live.record_progress(str(task.pk), progress,
                             f"Interval {len(intervals)}{f'/{total}' if total else ''}: "
                             f"{last['fake_prob'] * 100:.0f}% fake", log=True)
    for row in rows:
        transaction.on_commit(lambda r=row: publish_job(job, "task.interval", {
            "job_id": str(job.pk), "interval": {k: r[k] for k in ("index", "start_sec", "end_sec", "fake_prob")}}))
    push_job_state(job)
    return {"ok": True, "continue": True}


def _on_finished(session: StreamSession, job: Job, task: JobTask, payload: dict[str, Any]) -> dict[str, Any]:
    now = timezone.now()
    status = str(payload.get("status") or "error")
    intervals = sorted((_interval(r) for r in payload.get("intervals") or []), key=lambda i: i["index"])
    if not intervals:
        intervals = (task.result or {}).get("intervals", [])
    analysed = min(_analysed(intervals), session.reserved_seconds + RANGE_TOLERANCE)
    session.analysed_seconds = analysed
    session.status = StreamSession.Status.FINISHED
    session.finished_at = now
    session.save()

    task.finished_at = now
    task.progress = 100.0
    task.duration_ms = int((now - (task.started_at or now)).total_seconds() * 1000) or None
    job.finished_at = now
    job.progress = 100.0
    job.stage = "done"
    charged = 0
    if status == "error" or not intervals:
        # Nothing usable (or our failure): the user is not charged.
        if job.hold_id:
            credits.release(job.hold, memo="Long-form scan ended without results — not charged")
        if status == "error":
            code = "RUNTIME_ERROR"
            task.status, task.error_code, task.error_message = JobTask.Status.FAILED, code, user_message(code)
            task.error_detail = str(payload.get("error") or "")[:4000]
            job.status, job.error_code = Job.Status.FAILED, "ANALYSIS_FAILED"
            job.error_message = "The long-form scan failed. You were not charged."
        else:
            task.status, task.stage_message = JobTask.Status.CANCELED, "Stopped before any result"
            job.status = Job.Status.CANCELED
    else:
        average = max(0.0, min(1.0, float(payload.get("average") or 0.0)))
        charged = pricing.quote_long_video(analysed).credits if analysed > 0 else 0
        if job.hold_id:
            charged = credits.settle(job.hold, charged,
                                     memo=f"Long-form scan: {math.ceil(analysed / 60)} min analysed").amount
        threshold = PlatformSettings.load().fake_threshold
        task.status, task.stage_message = JobTask.Status.SUCCEEDED, "Done"
        task.result = {**(task.result or {}), "intervals": intervals, "fake_prob": round(average, 6),
                       "summary_statistic": payload.get("summary_statistic") or "mean"}
        job.status = Job.Status.SUCCEEDED
        job.fake_probability = round(average, 6)
        job.verdict = Job.Verdict.FAKE if average >= threshold else Job.Verdict.REAL
        job.partial = status == "stopped"
        job.credits_charged = charged
        job.verdict_reasons = [{"code": "model_consensus", "models": 1, "fake_probability": job.fake_probability}]
        if job.partial:
            job.verdict_reasons.append({"code": "stopped_early", "analysed_seconds": round(analysed, 1),
                                        "range_seconds": round(session.reserved_seconds, 1)})
    job.summary = {
        "models": [{"model": session.model_id, "name": session.model_name, "status": task.status,
                    "fake_prob": job.fake_probability, "no_face": False, "weight": 1.0,
                    "duration_ms": task.duration_ms, "fallback": None, "error_code": task.error_code}],
        "audit": {}, "ai_indicators": {},
        # One result group: the family of the long-form detector in use.
        "groups": [{"group": _family(session.model_id), "status": "done", "fake_probability": job.fake_probability,
                    "verdict": job.verdict}] if job.fake_probability is not None else [],
        "stream": {"status": status, "analysed_seconds": round(analysed, 1),
                   "range_seconds": round(session.reserved_seconds, 1), "intervals": len(intervals)},
    }
    task.save()
    job.save()
    level = "success" if job.status == Job.Status.SUCCEEDED else ("warning" if job.status == Job.Status.CANCELED
                                                                   else "error")
    minutes = math.ceil(analysed / 60) if analysed else 0
    message = {"done": f"Scan finished: {minutes} min analysed, {charged} credits charged",
               "stopped": f"Stopped after {minutes} min: {charged} credits charged",
               "error": "The scan failed; credits released"}.get(status, "Scan ended")
    emit(job, f"job.{job.status}", message, public=message, level=level,
         data={"verdict": job.verdict, "fake_probability": job.fake_probability, "credits_charged": charged})
    live.record_progress(str(task.pk), 100, message, log=True)
    push_job_state(job)
    return {"ok": True, "job_id": str(job.pk), "credits_charged": charged, "verdict": job.verdict}


# --- maintenance ------------------------------------------------------------------------------

def expire_stale_sessions() -> int:
    """Refund scans whose video never arrived, and scans whose service stopped reporting."""
    now = timezone.now()
    upload_cutoff = now - timedelta(minutes=settings.STREAM_UPLOAD_TIMEOUT_MINUTES)
    idle_cutoff = now - timedelta(minutes=settings.STREAM_IDLE_TIMEOUT_MINUTES)
    stale = (StreamSession.objects.filter(status=StreamSession.Status.CREATED, created_at__lt=upload_cutoff)
             | StreamSession.objects.filter(status=StreamSession.Status.RUNNING, last_event_at__lt=idle_cutoff))
    count = 0
    for session_id in stale.values_list("pk", flat=True):
        with transaction.atomic():
            session = StreamSession.objects.select_for_update().get(pk=session_id)
            if session.status not in (StreamSession.Status.CREATED, StreamSession.Status.RUNNING):
                continue
            job = Job.objects.select_for_update().get(pk=session.job_id)
            never_started = session.status == StreamSession.Status.CREATED
            session.status = StreamSession.Status.EXPIRED
            session.finished_at = now
            session.save(update_fields=["status", "finished_at", "updated_at"])
            if job.is_terminal:
                continue
            if job.hold_id:
                credits.release(job.hold, memo="Long-form scan did not complete — credits released")
            code = "QUEUE_TIMEOUT" if never_started else "WORKER_LOST"
            job.tasks.filter(queue=STREAM).update(status=JobTask.Status.FAILED if not never_started
                                                  else JobTask.Status.CANCELED, error_code=code,
                                                  error_message=user_message(code), finished_at=now)
            job.status = Job.Status.CANCELED if never_started else Job.Status.FAILED
            job.error_message = ("The video was never streamed; credits released." if never_started
                                 else "The scan stopped responding; credits released.")
            job.finished_at, job.progress, job.stage = now, 100.0, "done"
            job.save()
            emit(job, f"job.{job.status}", job.error_message, public=job.error_message, level="warning")
            push_job_state(job)
            count += 1
    return count
