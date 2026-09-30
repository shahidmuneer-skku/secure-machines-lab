"""Queue position and ETA for waiting tasks.

position = tasks ahead of it in the same queue (higher priority, or same
priority and older); ETA ≈ (position / consumers + 1) × p50 duration.
"""

from __future__ import annotations

import statistics
from typing import Any

from django.core.cache import cache
from django.db.models import Q

from .live import consumers_for
from .models import JobTask

DEFAULT_P50_MS = {"image": 15_000, "video": 120_000}


def p50_ms(queue: str, media_type: str) -> int:
    key = f"eta:p50:{queue}:{media_type}"
    value = cache.get(key)
    if value is None:
        durations = list(
            JobTask.objects.filter(queue=queue, media_type=media_type, status=JobTask.Status.SUCCEEDED,
                                   duration_ms__isnull=False)
            .order_by("-finished_at").values_list("duration_ms", flat=True)[:50]
        )
        value = int(statistics.median(durations)) if durations else DEFAULT_P50_MS.get(media_type, 30_000)
        cache.set(key, value, 60)
    return value


def queue_info(task: JobTask) -> dict[str, Any] | None:
    if task.status not in (JobTask.Status.PENDING, JobTask.Status.DISPATCHED):
        return None
    ahead = JobTask.objects.filter(
        queue=task.queue, status__in=[JobTask.Status.PENDING, JobTask.Status.DISPATCHED, JobTask.Status.RUNNING],
    ).filter(Q(priority__gt=task.priority) | Q(priority=task.priority, created_at__lt=task.created_at)).count()
    consumers = consumers_for(task.queue)
    p50 = p50_ms(task.queue, task.media_type)
    eta_ms = int((ahead / max(consumers, 1) + 1) * p50)
    return {"position": ahead + 1, "consumers": consumers, "eta_seconds": eta_ms // 1000,
            "workers_online": consumers > 0}
