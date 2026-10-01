"""Per-task context handed to adapters: progress, live log lines, cancellation, artifacts.

Progress and log lines go to Redis (hash + capped list) and are pushed live to
the user's SSE channel. Nothing here touches the database; the API persists
only the final result sent through the results queue.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis

from .clients import redis_client, upload

logger = logging.getLogger(__name__)

PROGRESS_KEY = "sml:task-progress:{}"
LOG_KEY = "sml:task-log:{}"
CANCEL_KEY = "sml:cancel:{}"
USER_CHANNEL = "sml:events:user:{}"
JOB_CHANNEL = "sml:events:job:{}"
TTL_SECONDS = 24 * 3600
PUBLISH_INTERVAL = 0.75
ACTIVITY_INTERVAL = 2.0
# Absolute filesystem paths (not URLs or fractions) are shortened even in the operators' live log.
_PATH = re.compile(r"(?<![\w:/.])(?:/[^\s/'\"`:,;()\[\]{}<>]+){2,}")


def redact_paths(text: str) -> str:
    """Replace absolute paths with their last component, e.g. /home/x/w/model.pt -> …/model.pt."""
    return _PATH.sub(lambda m: "…/" + m.group(0).rsplit("/", 1)[-1], text)


class Canceled(Exception):
    """Raised inside adapters when the user canceled the job."""


@dataclass
class ArtifactOut:
    kind: str  # xai | face | video | frames | other
    label: str
    storage_key: str
    content_type: str
    size_bytes: int
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "storage_key": self.storage_key,
                "content_type": self.content_type, "size_bytes": self.size_bytes, "meta": self.meta}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskContext:
    def __init__(self, envelope: dict[str, Any], workdir: Path, gpu: str | None):
        self.envelope = envelope
        self.task_id: str = envelope.get("task_id") or envelope.get("explanation_id") or ""
        self.job_id: str = envelope.get("job_id", "")
        self.user_id: str | None = envelope.get("user_id")
        self.workdir = workdir
        self.gpu = gpu
        self.artifacts: list[ArtifactOut] = []
        self._last_publish = 0.0
        self._last_activity = 0.0
        self._last_cancel_check = 0.0
        self._progress = 0.0
        self._redis: redis.Redis | None = None
        try:
            self._redis = redis_client()
        except redis.RedisError:
            logger.warning("Redis unavailable; progress will not stream")

    # --- progress & log -----------------------------------------------------------

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        if self._redis is None:
            return
        payload = json.dumps({"type": event_type, "ts": _now(), "data": data})
        try:
            if self.user_id:
                self._redis.publish(USER_CHANNEL.format(self.user_id), payload)
            if self.job_id:
                self._redis.publish(JOB_CHANNEL.format(self.job_id), payload)
        except redis.RedisError:
            pass

    def progress(self, percent: float, message: str | None = None, *, force: bool = False) -> None:
        percent = max(0.0, min(100.0, float(percent)))
        self._progress = max(self._progress, percent)
        now = time.monotonic()
        if not force and now - self._last_publish < PUBLISH_INTERVAL:
            return
        self._last_publish = now
        if self._redis is not None:
            try:
                key = PROGRESS_KEY.format(self.task_id)
                mapping = {"progress": f"{self._progress:.1f}", "updated_at": _now()}
                if message:
                    mapping["message"] = message[:240]
                self._redis.hset(key, mapping=mapping)
                self._redis.expire(key, TTL_SECONDS)
            except redis.RedisError:
                pass
        # Users must not learn which detectors run: subscribers only hear that the job moved on and
        # refetch its user-safe view. Progress values and messages stay in Redis for the API/admin.
        if now - self._last_activity >= ACTIVITY_INTERVAL:
            self._last_activity = now
            self._publish("job.activity", {"job_id": self.job_id})
        self.check_canceled()

    def log(self, message: str) -> None:
        """A line for the task's live log (admin console only; users see generic job steps)."""
        logger.info("[%s] %s", self.task_id[:8], message.strip()[:1000])
        message = redact_paths(message.strip())[:300]
        if not message:
            return
        if self._redis is not None:
            try:
                key = LOG_KEY.format(self.task_id)
                self._redis.rpush(key, json.dumps({"at": _now(), "message": message}))
                self._redis.ltrim(key, -200, -1)
                self._redis.expire(key, TTL_SECONDS)
            except redis.RedisError:
                pass
        self.progress(self._progress, message, force=True)

    # --- cancellation -----------------------------------------------------------------

    def canceled(self) -> bool:
        if self._redis is None or not self.job_id:
            return False
        try:
            return bool(self._redis.exists(CANCEL_KEY.format(self.job_id)))
        except redis.RedisError:
            return False

    def check_canceled(self) -> None:
        now = time.monotonic()
        if now - self._last_cancel_check < 2.0:
            return
        self._last_cancel_check = now
        if self.canceled():
            raise Canceled()

    # --- artifacts ------------------------------------------------------------------------

    def add_artifact(self, path: Path, *, kind: str, label: str, meta: dict[str, Any] | None = None) -> None:
        key = f"jobs/{self.job_id}/{self.task_id}/{len(self.artifacts):02d}_{path.name}"
        try:
            key, content_type, size = upload(path, key)
            self.artifacts.append(ArtifactOut(kind, label, key, content_type, size, meta or {}))
        except Exception:
            logger.warning("Artifact upload failed for %s", path, exc_info=True)
