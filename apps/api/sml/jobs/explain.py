"""On-demand "Explain why" requests handled by the reasoning worker."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from sml.core.events import publish_job
from sml.core.exceptions import Conflict
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.credits import services as credits
from sml.queues import REASONING, WORKER_TASK

from .models import Explanation, Job

logger = logging.getLogger(__name__)


def request_explanation(job: Job, user: Any, locale: str) -> Explanation:
    if job.status != Job.Status.SUCCEEDED or job.purged_at:
        raise Conflict("Explanations are available for completed jobs whose media is still retained.")
    running = job.explanations.filter(status__in=[Explanation.Status.QUEUED, Explanation.Status.RUNNING]).first()
    if running:
        return running
    cfg = PlatformSettings.load()
    cost = pricing.quote_explain().credits
    with transaction.atomic():
        exp = Explanation.objects.create(job=job, user=user, engine=cfg.reasoning_engine,
                                         model_name=cfg.reasoning_model, locale=locale)
        exp.hold = credits.reserve(user, cost, reference_type="explain", reference_id=str(exp.pk))
        exp.save(update_fields=["hold"])
        transaction.on_commit(lambda: _publish(exp))
    return exp


def _context(job: Job) -> dict[str, Any]:
    return {
        "verdict": job.verdict, "fake_probability": job.fake_probability, "media_type": job.media_type,
        "file_name": job.title, "summary": job.summary, "reasons": job.verdict_reasons,
        "artifacts": [{"kind": a.kind, "label": a.label, "storage_key": a.storage_key}
                      for a in job.artifacts.filter(kind__in=["xai", "face"])[:8]],
    }


def _publish(exp: Explanation) -> None:
    from sml.celery import app

    job = exp.job
    media = job.media
    envelope = {
        "v": 1, "kind": "explain", "explanation_id": str(exp.pk), "job_id": str(job.pk),
        "user_id": str(exp.user_id), "engine": exp.engine, "model": exp.model_name, "locale": exp.locale,
        "media": {"storage_key": media.storage_key, "extension": media.extension,
                  "original_name": media.original_name} if media else None,
        "context": _context(job),
    }
    app.send_task(WORKER_TASK, args=[envelope], queue=REASONING, routing_key=REASONING, priority=5)


def record_explanation_event(payload: dict[str, Any]) -> None:
    with transaction.atomic():
        exp = Explanation.objects.select_for_update().select_related("job").filter(
            pk=payload.get("explanation_id")).first()
        if exp is None or exp.status in (Explanation.Status.SUCCEEDED, Explanation.Status.FAILED):
            return
        event = payload.get("event")
        if event == "started":
            exp.status = Explanation.Status.RUNNING
            exp.started_at = timezone.now()
        elif event == "progress":
            exp.progress_log = (exp.progress_log + [payload.get("message", "")])[-50:]
        elif event == "finished":
            exp.finished_at = timezone.now()
            if payload.get("status") == "succeeded" and payload.get("content"):
                exp.status = Explanation.Status.SUCCEEDED
                exp.content = str(payload["content"])[:50_000]
                if exp.hold_id:
                    exp.credits_charged = credits.capture(exp.hold, memo="Explain why").amount
            else:
                exp.status = Explanation.Status.FAILED
                exp.error_message = str(payload.get("error_message") or "Reasoning failed")[:500]
                if exp.hold_id:
                    credits.release(exp.hold, memo="Explanation failed — not charged")
        exp.save()
        job = exp.job
        data = {"explanation_id": str(exp.pk), "job_id": str(job.pk), "status": exp.status,
                "message": payload.get("message", "")}
        transaction.on_commit(lambda: publish_job(job, "explanation.updated", data))
