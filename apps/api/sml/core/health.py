"""Dependency checks shared by the readiness probe and the admin system page.

Each check returns a status ("ok" or "error") and how long it took. Failures are logged here
and reported without their exception text, which may contain hostnames or credentials.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import redis
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection

logger = logging.getLogger(__name__)


def _database() -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT 1")


def _redis() -> None:
    redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping()


def _broker() -> None:
    from sml.celery import app

    with app.connection_for_write() as conn:
        conn.ensure_connection(max_retries=1, timeout=2)


def _storage() -> None:
    bucket = getattr(default_storage, "bucket", None)
    if bucket is not None:  # S3: the bucket must exist and the credentials must work
        bucket.meta.client.head_bucket(Bucket=bucket.name)
    else:
        default_storage.listdir("")


CORE_CHECKS: dict[str, Callable[[], None]] = {"database": _database, "redis": _redis, "broker": _broker}
ALL_CHECKS: dict[str, Callable[[], None]] = {**CORE_CHECKS, "storage": _storage}


def run_checks(checks: dict[str, Callable[[], None]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, check in checks.items():
        started = time.monotonic()
        try:
            check()
            status = "ok"
        except Exception:  # a health check reports failures, never raises
            logger.warning("Health check %s failed", name, exc_info=True)
            status = "error"
        results[name] = {"status": status, "latency_ms": round((time.monotonic() - started) * 1000)}
    return results
