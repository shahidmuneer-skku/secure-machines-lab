"""Live event fan-out (Redis pub/sub) consumed by the SSE endpoint.

Channels:
  sml:events:user:<user_id>   everything a signed-in user should see live
  sml:events:job:<job_id>     per-job channel (guest trial pages poll/stream this)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

USER_CHANNEL = "sml:events:user:{}"
JOB_CHANNEL = "sml:events:job:{}"

# In tests we collect events in memory instead of talking to Redis.
memory_events: list[tuple[str, dict[str, Any]]] = []


@lru_cache(maxsize=1)
def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


def publish(channel: str, event_type: str, data: dict[str, Any]) -> None:
    payload = {"type": event_type, "ts": datetime.now(UTC).isoformat(), "data": data}
    if getattr(settings, "EVENTS_BACKEND", "redis") == "memory":
        memory_events.append((channel, payload))
        return
    try:
        _client().publish(channel, json.dumps(payload, default=str))
    except redis.RedisError:
        # Live updates are best-effort; clients fall back to polling.
        logger.warning("Failed to publish %s on %s", event_type, channel, exc_info=True)


def publish_to_user(user_id: Any, event_type: str, data: dict[str, Any]) -> None:
    if user_id:
        publish(USER_CHANNEL.format(user_id), event_type, data)


def publish_job(job: Any, event_type: str, data: dict[str, Any]) -> None:
    publish(JOB_CHANNEL.format(job.pk), event_type, data)
    publish_to_user(job.user_id, event_type, data)
