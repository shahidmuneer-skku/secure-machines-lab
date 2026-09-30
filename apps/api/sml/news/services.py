from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from sml.catalog import access
from sml.catalog.registry import registry
from sml.core.exceptions import ApiError
from sml.core.models import PlatformSettings
from sml.credits import pricing
from sml.credits import services as credits
from sml.jobs.models import Job, JobTask
from sml.jobs.retention import priority_for, retention_days_for
from sml.jobs.services import _after_commit_dispatch, _check_platform
from sml.jobs.timeline import emit, push_job_state
from sml.media.models import MediaObject
from sml.queues import MODEL_PREFIX, NEWS

from .models import NewsCase

MAX_MEDIA = 10
# Detectors run on each attached file before the agent starts (legacy default: SKKU-AIGC).
FORENSIC_MODELS = {"image": ["skku-aigc"], "video": ["skku-aigc"]}


def create_news_job(user: Any, data: dict[str, Any], media: list[MediaObject], *, source: str = "web",
                    api_key: Any = None, locale: str = "en") -> Job:
    _check_platform()
    access.assert_module_allowed(user, "news")
    if len(media) > MAX_MEDIA:
        raise ApiError(f"At most {MAX_MEDIA} media files per case.")
    if any(m.status != MediaObject.Status.READY for m in media):
        raise ApiError("All attached media must be fully uploaded.")
    cfg = PlatformSettings.load()
    quote = pricing.quote_news()
    priority = priority_for(user, source)
    reg = registry()
    with transaction.atomic():
        job = Job.objects.create(
            user=user, api_key=api_key if hasattr(api_key, "prefix") else None, source=source, kind=Job.Kind.NEWS,
            media=media[0] if media else None, media_type=media[0].media_type if media else "",
            title=data["title"][:255], locale=locale, priority=priority, credits_quoted=quote.credits,
            quote_lines=[{"label": ln.label, "credits": ln.credits} for ln in quote.lines],
            options={"engine": cfg.news_engine, "model": cfg.news_model},
            expires_at=timezone.now() + timedelta(days=retention_days_for(user)),
        )
        case = NewsCase.objects.create(job=job, **{k: data.get(k, "") for k in (
            "title", "location", "category", "violence_level", "description", "social_media_link")})
        case.media.set(media)
        job.options["news_case_id"] = str(case.pk)
        job.hold = credits.reserve(user, quote.credits, reference_type="job", reference_id=str(job.pk))
        job.save(update_fields=["options", "hold"])
        for m in media:
            for model_id in FORENSIC_MODELS.get(m.media_type, []):
                spec = reg.get(model_id)
                if spec and spec.enabled and spec.supports(m.media_type) and access.model_allowed(user, spec, api_key):
                    JobTask.objects.create(job=job, kind=JobTask.Kind.MODEL, target=model_id, media=m,
                                           media_type=m.media_type, queue=MODEL_PREFIX + model_id,
                                           priority=priority, max_attempts=1)
        JobTask.objects.create(job=job, kind=JobTask.Kind.NEWS, target=cfg.news_engine, queue=NEWS,
                               priority=priority, max_attempts=1, wait_for_models=True)
        emit(job, "job.created", f"News verification case created: {job.title}")
        emit(job, "credits.reserved", f"{quote.credits} credits reserved")
        emit(job, "job.queued", "Forensic detectors run first, then the verification agent")
        push_job_state(job)
        _after_commit_dispatch()
    return job
