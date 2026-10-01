"""Live task progress kept in Redis by workers (never persisted row-by-row)."""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

import redis
from django.conf import settings

from sml.core.events import _client

logger = logging.getLogger(__name__)

PROGRESS_KEY = "sml:task-progress:{}"
LOG_KEY = "sml:task-log:{}"
CANCEL_KEY = "sml:cancel:{}"
RESULT_KEY = "sml:task-result:{}"  # final results kept by workers (sml_worker/runner.py)
WORKER_KEY_PATTERN = "sml:worker:*"


def _redis() -> redis.Redis | None:
    if getattr(settings, "EVENTS_BACKEND", "redis") == "memory":
        return None
    return _client()


def redis_or_none() -> redis.Redis | None:
    """The Redis holding live state, or None when events are kept in memory (tests)."""
    return _redis()


def kept_results(task_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Final results the workers kept for the given tasks (see tasks.replay_kept_results)."""
    r = _redis()
    if r is None or not task_ids:
        return {}
    out: dict[str, dict[str, Any]] = {}
    try:
        for task_id, raw in zip(task_ids, r.mget([RESULT_KEY.format(t) for t in task_ids]), strict=True):
            if raw:
                with contextlib.suppress(ValueError):
                    out[task_id] = json.loads(raw)
    except redis.RedisError:
        logger.warning("Redis unavailable for kept results", exc_info=True)
    return out


def task_progress(task_ids: list[str]) -> dict[str, dict[str, Any]]:
    r = _redis()
    if r is None or not task_ids:
        return {}
    try:
        pipe = r.pipeline()
        for tid in task_ids:
            pipe.hgetall(PROGRESS_KEY.format(tid))
        out: dict[str, dict[str, Any]] = {}
        for tid, raw in zip(task_ids, pipe.execute(), strict=True):
            if raw:
                out[tid] = {k.decode(): v.decode() for k, v in raw.items()}
        return out
    except redis.RedisError:
        logger.warning("Redis unavailable for live progress", exc_info=True)
        return {}


def record_progress(task_id: str, progress: float, message: str = "", *, log: bool = False,
                    ttl: int = 24 * 3600) -> None:
    """Write live progress (and optionally a log line) the way workers do, for tasks run elsewhere."""
    r = _redis()
    if r is None:
        return
    from django.utils import timezone

    now = timezone.now().isoformat()
    try:
        pipe = r.pipeline()
        key = PROGRESS_KEY.format(task_id)
        pipe.hset(key, mapping={"progress": f"{max(0.0, min(100.0, progress)):.1f}", "updated_at": now,
                                **({"message": message[:240]} if message else {})})
        pipe.expire(key, ttl)
        if log and message:
            log_key = LOG_KEY.format(task_id)
            pipe.rpush(log_key, json.dumps({"at": now, "message": message[:300]}))
            pipe.ltrim(log_key, -200, -1)
            pipe.expire(log_key, ttl)
        pipe.execute()
    except redis.RedisError:
        logger.warning("Redis unavailable for live progress", exc_info=True)


def task_log(task_id: str, limit: int = 100) -> list[dict[str, Any]]:
    r = _redis()
    if r is None:
        return []
    try:
        return [json.loads(x) for x in r.lrange(LOG_KEY.format(task_id), -limit, -1)]
    except (redis.RedisError, ValueError):
        return []


def request_cancel(job_id: str, ttl: int = 6 * 3600) -> None:
    r = _redis()
    if r is not None:
        try:
            r.set(CANCEL_KEY.format(job_id), "1", ex=ttl)
        except redis.RedisError:
            logger.warning("Could not set cancel flag for %s", job_id)


def workers() -> list[dict[str, Any]]:
    """Worker heartbeats (TTL'd keys written by sml_worker every few seconds)."""
    r = _redis()
    if r is None:
        return []
    try:
        keys = list(r.scan_iter(WORKER_KEY_PATTERN, count=200))
        values = r.mget(keys) if keys else []
        return [json.loads(v) for v in values if v]
    except (redis.RedisError, ValueError):
        return []


def consumers_for(queue: str) -> int:
    return sum(1 for w in workers() if queue in w.get("queues", []))
