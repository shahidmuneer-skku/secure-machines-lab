"""Consumes worker events, then aggregates finished jobs into one verdict and settles credits.

Charging rule (flat per file, ADR 0006): a job is charged its quoted price only
when at least one model produced a score. No-face-only results, failures on our
side and cancellations are released (refunded) in full.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from sml.catalog.registry import registry
from sml.core.models import PlatformSettings
from sml.credits import services as credits

from .errors import user_message
from .models import Artifact, Job, JobTask
from .timeline import emit, push_job_state

logger = logging.getLogger(__name__)

TASK_WEIGHT = {JobTask.Kind.MODEL: 1.0, JobTask.Kind.LONG_VIDEO: 1.0, JobTask.Kind.NEWS: 1.0,
               JobTask.Kind.AUDIT: 0.25}
RETRYABLE_CODES = {"WORKER_LOST", "TIMEOUT", "GPU_OOM", "RUNTIME_ERROR", "INFRA_ERROR"}

# What users see when a step starts. They never learn which detectors run or how many.
PUBLIC_CHECK_STARTED = {
    "metadata": "Checking file metadata and provenance",
    "face": "Looking for faces",
    "safety": "Checking content safety",
    "fas": "Checking face liveness",
}


def _public_start(job: Job, task: JobTask, first_start: bool) -> str:
    if task.kind == JobTask.Kind.AUDIT:
        return PUBLIC_CHECK_STARTED.get(task.target, "") if first_start else ""
    if task.kind == JobTask.Kind.NEWS:
        return "Verifying the story" if first_start else ""
    # Detectors (and long-form scans): one message when the analysis begins, not one per detector.
    started = job.tasks.filter(kind__in=[JobTask.Kind.MODEL, JobTask.Kind.LONG_VIDEO],
                               started_at__isnull=False).exclude(pk=task.pk).exists()
    if not first_start or started:
        return ""
    if job.kind == Job.Kind.NEWS:
        return "Analysing the attached media"
    return f"Analysing the {job.media_type or 'file'}"


# --- normalization ---------------------------------------------------------------

def _prob(value: Any) -> float | None:
    """Accepts 0-1 or 0-100 and returns 0-1."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v > 1.0:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw or {})
    if "fake_prob" in out:
        out["fake_prob"] = _prob(out["fake_prob"])
    if out.get("fake_prob") is not None:
        out["real_prob"] = round(1.0 - out["fake_prob"], 6)
    out["no_face"] = bool(out.get("no_face", False))
    return out


# --- progress -------------------------------------------------------------------

def recompute_progress(job: Job) -> None:
    tasks = list(job.tasks.all())
    if not tasks:
        return
    total = sum(TASK_WEIGHT.get(t.kind, 1.0) for t in tasks)
    done = sum(TASK_WEIGHT.get(t.kind, 1.0) * (100.0 if t.is_terminal else t.progress) for t in tasks)
    job.progress = round(done / total, 1) if total else 0.0
    if any(t.status == JobTask.Status.RUNNING for t in tasks):
        job.stage = "analyzing"
    elif all(t.is_terminal for t in tasks):
        job.stage = "aggregating"
    else:
        job.stage = "queued" if job.status == Job.Status.QUEUED else "analyzing"


# --- worker events ----------------------------------------------------------------

def record_task_event(payload: dict[str, Any]) -> None:
    event = payload.get("event")
    task_id = payload.get("task_id")
    with transaction.atomic():
        task = JobTask.objects.select_for_update().select_related("job").filter(pk=task_id).first()
        if task is None:
            logger.warning("Event for unknown task %s", task_id)
            return
        if int(payload.get("attempt", task.attempt)) != task.attempt:
            logger.info("Ignoring stale event for task %s (attempt %s != %s)", task_id,
                        payload.get("attempt"), task.attempt)
            return
        job = Job.objects.select_for_update().get(pk=task.job_id)
        if event == "started":
            _on_started(job, task, payload)
        elif event == "finished":
            _on_finished(job, task, payload)
        else:
            logger.warning("Unknown task event %r", event)
            return
        recompute_progress(job)
        job.save(update_fields=["status", "stage", "progress", "started_at", "updated_at"])
        push_job_state(job)
        if all(t.is_terminal for t in job.tasks.all()):
            finalize_job(job)
    from .tasks import dispatch

    transaction.on_commit(lambda: dispatch.delay())


def _on_started(job: Job, task: JobTask, payload: dict[str, Any]) -> None:
    if task.is_terminal:
        return
    first_start = task.started_at is None  # a retry starts the same task again
    task.status = JobTask.Status.RUNNING
    task.started_at = parse_datetime(payload.get("at") or "") or timezone.now()
    task.worker = str(payload.get("worker", ""))[:128]
    task.gpu = str(payload.get("gpu", ""))[:32]
    task.stage_message = "Running"
    task.save(update_fields=["status", "started_at", "worker", "gpu", "stage_message", "updated_at"])
    if job.status == Job.Status.QUEUED:
        job.status = Job.Status.RUNNING
        job.started_at = task.started_at
    where = f" on GPU {task.gpu}" if task.gpu else ""
    emit(job, "task.started", f"{task.get_kind_display()} '{task.target}' started{where}", task=task,
         public=_public_start(job, task, first_start), data={"worker": task.worker, "gpu": task.gpu})


def _on_finished(job: Job, task: JobTask, payload: dict[str, Any]) -> None:
    if task.is_terminal:
        return
    status = payload.get("status")
    now = timezone.now()
    task.finished_at = now
    task.duration_ms = int(payload.get("duration_ms") or 0) or None
    task.progress = 100.0
    for art in payload.get("artifacts", []) or []:
        Artifact.objects.create(
            job=job, task=task, kind=art.get("kind", Artifact.Kind.OTHER), label=str(art.get("label", ""))[:128],
            storage_key=art["storage_key"], content_type=art.get("content_type", "application/octet-stream"),
            size_bytes=int(art.get("size_bytes") or 0), meta=art.get("meta") or {},
        )

    if status == "succeeded":
        task.status = JobTask.Status.SUCCEEDED
        task.result = normalize_result(payload.get("result") or {})
        task.stage_message = "Done"
        task.save()
        _emit_success(job, task)
        return

    if status == "canceled":
        task.status = JobTask.Status.CANCELED
        task.stage_message = "Canceled"
        task.save()
        emit(job, "task.canceled", f"'{task.target}' canceled", task=task, level="warning")
        return

    code = str(payload.get("error_code") or "RUNTIME_ERROR")[:64]
    message = user_message(code)
    task.error_code, task.error_message = code, message
    task.error_detail = str(payload.get("error_message") or "")[:4000]
    if code in RETRYABLE_CODES and task.attempt < task.max_attempts and not job.cancel_requested:
        task.status = JobTask.Status.PENDING
        task.stage_message = "Retrying"
        task.finished_at = None
        task.progress = 0.0
        task.save()
        emit(job, "task.retry", f"'{task.target}' failed ({code}); retrying", task=task, level="warning")
        return
    task.status = JobTask.Status.FAILED
    task.stage_message = "Failed"
    task.save()
    emit(job, "task.failed", f"'{task.target}' failed: {message}", task=task, level="error",
         data={"error_code": code})
    _maybe_fallback(job, task, code)


def _emit_success(job: Job, task: JobTask) -> None:
    r = task.result
    if task.kind == JobTask.Kind.AUDIT:
        emit(job, "audit.done", f"Audit step '{task.target}' completed", task=task, level="success")
        return
    if r.get("no_face"):
        emit(job, "task.no_face", f"'{task.target}': no face found in the media", task=task, level="warning")
    elif r.get("fake_prob") is not None:
        emit(job, "task.succeeded", f"'{task.target}' finished: {r['fake_prob'] * 100:.1f}% fake", task=task,
             level="success", data={"fake_prob": r["fake_prob"]})
    fb = r.get("fallback")
    if fb:
        emit(job, "task.fallback", f"'{task.target}' used fallback model '{fb.get('model')}' ({fb.get('reason')})",
             task=task, level="warning", data=fb)


def _maybe_fallback(job: Job, task: JobTask, code: str) -> None:
    if task.kind != JobTask.Kind.MODEL or task.fallback_for_id or job.cancel_requested:
        return
    spec = registry().get(task.target)
    target = (spec.fallbacks or {}).get("on_runtime_error") if spec else None
    fb = registry().get(target) if target else None
    if fb is None or not fb.enabled or not fb.supports(task.media_type):
        return
    if job.tasks.filter(kind=JobTask.Kind.MODEL, target=fb.id).exists():
        return
    JobTask.objects.create(job=job, kind=JobTask.Kind.MODEL, target=fb.id, media_type=task.media_type,
                           queue=fb.queue, priority=task.priority, fallback_for=task, max_attempts=1)
    emit(job, "task.fallback_scheduled", f"'{task.target}' failed; running fallback '{fb.id}'", level="warning")


# --- aggregation -------------------------------------------------------------------

def _metadata_flags(indicators: dict[str, Any], *, detectors_say_fake: bool) -> bool:
    """Whether metadata marks the file "likely AI-generated" (owner's rule, 2026-10-01).

    Definite markers (C2PA / IPTC AI declaration, embedded generation parameters, a generator
    software tag) always do. Weak hints (a generator merely mentioned somewhere in the metadata)
    only label a file the detectors already judged fake; otherwise the detectors' verdict stands
    and the hint is shown as evidence.
    """
    if indicators.get("ai_generated"):
        return True
    return detectors_say_fake and bool(indicators.get("evidence"))


def _metadata_indicators(job: Job) -> dict[str, Any]:
    meta = job.tasks.filter(kind=JobTask.Kind.AUDIT, target="metadata", status=JobTask.Status.SUCCEEDED).first()
    return (meta.result or {}).get("ai_indicators", {}) if meta else {}


def finalize_job(job: Job) -> Job:
    """Idempotent: settles a job whose tasks are all terminal."""
    if job.is_terminal:
        return job
    tasks = list(job.tasks.all())
    if any(not t.is_terminal for t in tasks):
        return job
    reg = registry()
    threshold = PlatformSettings.load().fake_threshold
    scored = [t for t in tasks if t.kind in (JobTask.Kind.MODEL, JobTask.Kind.LONG_VIDEO, JobTask.Kind.NEWS)]
    usable = [t for t in scored if t.status == JobTask.Status.SUCCEEDED and not t.result.get("no_face")
              and t.result.get("fake_prob") is not None]
    no_face = [t for t in scored if t.status == JobTask.Status.SUCCEEDED and t.result.get("no_face")]
    failed = [t for t in scored if t.status == JobTask.Status.FAILED]
    indicators = _metadata_indicators(job)

    per_model = []
    for t in scored:
        spec = reg.get(t.target)
        per_model.append({
            "model": t.target, "name": spec.name(job.locale) if spec else t.target, "status": t.status,
            "fake_prob": t.result.get("fake_prob"), "no_face": bool(t.result.get("no_face")),
            "weight": spec.weight if spec else 1.0, "duration_ms": t.duration_ms,
            "fallback": t.result.get("fallback"), "error_code": t.error_code,
        })
    audits = {t.target: {"status": t.status, "result": t.result} for t in tasks if t.kind == JobTask.Kind.AUDIT}
    job.summary = {"models": per_model, "audit": audits, "ai_indicators": indicators}
    job.finished_at = timezone.now()
    job.progress = 100.0
    job.stage = "done"
    reasons: list[dict[str, Any]] = []

    news = next((t for t in tasks if t.kind == JobTask.Kind.NEWS), None)
    if job.cancel_requested:
        job.status = Job.Status.CANCELED
        job.verdict = ""
        _release(job, "Job canceled — credits released")
    elif news is not None:
        _finalize_news(job, news, reasons)
    elif usable:
        weights = [(reg.get(t.target).weight if reg.get(t.target) else 1.0) for t in usable]
        prob = sum(w * t.result["fake_prob"] for w, t in zip(weights, usable, strict=True)) / (sum(weights) or 1)
        job.fake_probability = round(prob, 6)
        job.verdict = Job.Verdict.FAKE if prob >= threshold else Job.Verdict.REAL
        reasons.append({"code": "model_consensus", "models": len(usable), "fake_probability": job.fake_probability})
        if _metadata_flags(indicators, detectors_say_fake=job.verdict == Job.Verdict.FAKE):
            job.verdict = Job.Verdict.FAKE
            reasons.append({"code": "metadata_ai_indicator", "strength": indicators.get("confidence"),
                            "evidence": indicators.get("evidence", [])})
        job.partial = bool(failed)
        job.status = Job.Status.SUCCEEDED
        _capture(job)
    elif no_face and not failed:
        job.status = Job.Status.SUCCEEDED
        job.verdict = Job.Verdict.NO_FACE
        reasons.append({"code": "no_face"})
        if _metadata_flags(indicators, detectors_say_fake=False):
            job.verdict = Job.Verdict.FAKE
            reasons.append({"code": "metadata_ai_indicator", "strength": indicators.get("confidence"),
                            "evidence": indicators.get("evidence", [])})
        _release(job, "No face found — not charged")
    else:
        job.status = Job.Status.FAILED
        job.error_code = "ANALYSIS_FAILED"
        job.error_message = "The analysis could not be completed. You were not charged."
        _release(job, "Analysis failed — credits released")
    job.verdict_reasons = reasons
    job.save()
    level = "success" if job.status == Job.Status.SUCCEEDED else ("warning" if job.status == Job.Status.CANCELED
                                                                   else "error")
    message = _final_message(job)
    emit(job, f"job.{job.status}", message, public=message, level=level,
         data={"verdict": job.verdict, "fake_probability": job.fake_probability})
    push_job_state(job)
    return job


def _finalize_news(job: Job, news: JobTask, reasons: list[dict[str, Any]]) -> None:
    if news.status != JobTask.Status.SUCCEEDED:
        job.status = Job.Status.FAILED
        job.error_code = "NEWS_VERIFICATION_FAILED"
        job.error_message = news.error_message or "The verification agent could not complete this case."
        _release(job, "News verification failed — credits released")
        return
    meta = news.result.get("meta") or {}
    auth = meta.get("authenticity") or {}
    verdict = str(auth.get("verdict", "")).lower()
    job.verdict = {"fake": Job.Verdict.FAKE, "real": Job.Verdict.REAL}.get(verdict, Job.Verdict.INCONCLUSIVE)
    try:
        confidence = float(auth.get("confidence", 0)) / 100.0
    except (TypeError, ValueError):
        confidence = 0.0
    if job.verdict == Job.Verdict.FAKE:
        job.fake_probability = round(confidence, 4)
    elif job.verdict == Job.Verdict.REAL:
        job.fake_probability = round(1 - confidence, 4)
    job.summary["news"] = {"status": meta.get("status"), "confidence": meta.get("confidence"),
                           "report_markdown": news.result.get("report_markdown", ""), "meta": meta}
    reasons.append({"code": "news_agent", "status": meta.get("status"), "reasoning": auth.get("reasoning", "")})
    job.status = Job.Status.SUCCEEDED
    _capture(job)


def _final_message(job: Job) -> str:
    if job.status == Job.Status.SUCCEEDED and job.fake_probability is not None:
        label = "Likely manipulated" if job.verdict == Job.Verdict.FAKE else "Likely authentic"
        return f"Analysis complete: {label} ({job.fake_probability * 100:.1f}% fake)"
    if job.verdict == Job.Verdict.NO_FACE:
        return "Analysis complete: no face detected"
    if job.status == Job.Status.CANCELED:
        return "Job canceled"
    return "Analysis failed"


def _capture(job: Job) -> None:
    if job.hold_id:
        hold = credits.capture(job.hold, memo=f"Detection: {job.title}"[:255])
        job.credits_charged = hold.amount
        if hold.amount:
            message = f"{hold.amount} credits charged"
            emit(job, "credits.charged", message, public=message, level="info")


def _release(job: Job, memo: str) -> None:
    if job.hold_id:
        hold = credits.release(job.hold, memo=memo)
        job.credits_charged = 0
        if hold.amount:
            message = f"{hold.amount} credits returned to your balance"
            emit(job, "credits.released", message, public=message, level="info")
