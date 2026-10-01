from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.db.models import Max

from sml.core.events import publish_to_user
from sml.core.exceptions import Conflict
from sml.jobs import public
from sml.jobs.models import Explanation, Job
from sml.media import storage

from . import generators
from .models import Report

logger = logging.getLogger(__name__)
CONTENT_TYPES = {"pdf": "application/pdf", "hwp": "application/x-hwp", "csv": "text/csv; charset=utf-8",
                 "zip": "application/zip"}


def request_report(job: Job, user: Any, fmt: str, locale: str) -> Report:
    if job.status != Job.Status.SUCCEEDED:
        raise Conflict("Reports are available for completed jobs.")
    if job.purged_at and fmt == "zip":
        raise Conflict("Artifacts for this job have expired; a ZIP bundle is no longer available.")
    with transaction.atomic():
        latest = job.reports.filter(format=fmt, locale=locale).aggregate(v=Max("version"))["v"] or 0
        report = Report.objects.create(job=job, user=user, format=fmt, locale=locale, run_number=job.run_number,
                                       version=latest + 1)
        from .tasks import generate_report

        transaction.on_commit(lambda: generate_report.delay(str(report.pk)))
    return report


def _read(key: str) -> bytes | None:
    try:
        with storage.open_file(key) as fh:
            return fh.read()
    except Exception:  # noqa: BLE001 - missing media only drops the image from the report
        return None


def build_data(job: Job, locale: str) -> generators.ReportData:
    """Reports are handed to customers: they carry the verdict and evidence, never the detectors."""
    media = job.media
    tasks = list(job.tasks.all())
    xai: list[tuple[str, bytes]] = []
    for art in public.evidence_artifacts(job, tasks):
        data = _read(art.storage_key) if art.content_type.startswith("image/") else None
        if data and len(xai) < 6:
            xai.append((public.artifact_label(art), data))
    explanation = (job.explanations.filter(status=Explanation.Status.SUCCEEDED).order_by("-created_at")
                   .values_list("content", flat=True).first() or "")
    return generators.ReportData(
        locale=locale, job_id=str(job.pk), run_number=job.run_number, title=job.title, media_type=job.media_type,
        verdict=job.verdict, fake_probability=job.fake_probability, partial=job.partial,
        ai_generated=public.ai_generated(job), reasons=public.reasons(job), checks=public.checks(tasks),
        provenance=public.provenance(tasks),
        media={"size_bytes": media.size_bytes, "width": media.width, "height": media.height,
               "duration_seconds": media.duration_seconds, "sha256": media.sha256} if media else {},
        created_at=job.created_at, finished_at=job.finished_at,
        thumbnail=_read(media.thumbnail_key) if media and media.thumbnail_key else None,
        xai_images=xai, explanation=explanation,
    )


def generate(report: Report) -> Report:
    report.status = Report.Status.RUNNING
    report.save(update_fields=["status", "updated_at"])
    job = report.job
    try:
        data = build_data(job, report.locale)
        if report.format == "pdf":
            blob = generators.render_pdf(data)
        elif report.format == "hwp":
            blob = generators.render_hwp(data)
        elif report.format == "csv":
            blob = generators.render_csv(data)
        else:
            arts = []
            for art in public.evidence_artifacts(job):
                content = _read(art.storage_key)
                if content:
                    arts.append((public.artifact_filename(art), content))
            blob = generators.render_zip(data, arts)
        key = storage.save_bytes(f"reports/{job.pk}/{report.pk}.{report.format}", blob)
        report.storage_key = key
        report.size_bytes = len(blob)
        report.status = Report.Status.READY
    except Exception as exc:
        logger.exception("Report %s failed", report.pk)
        report.status = Report.Status.FAILED
        report.error_message = str(exc)[:255]
    report.save()
    publish_to_user(job.user_id, "report.updated", {"report_id": str(report.pk), "job_id": str(job.pk),
                                                     "status": report.status, "format": report.format})
    return report
