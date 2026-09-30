"""System snapshot for the admin overview: dependencies, services, GPUs and what waits for them.

The GPU and agent keys in Redis belong to the worker (apps/worker/sml_worker/gpu.py and
agents/ollama.py); this module only reads them. Everything here is best effort: a service that
cannot be reached is reported as "error", never raised.
"""

from __future__ import annotations

import contextlib
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import redis
from django.conf import settings

from sml.core.health import ALL_CHECKS, run_checks
from sml.core.models import PlatformSettings
from sml.jobs import live
from sml.jobs.models import StreamSession

GPU_RESERVATIONS = "sml:gpu-reservations:{host}:{gpu}"
GPU_WAITERS = "sml:gpu-waiters:{host}:{gpu}"
WAITER_ALIVE = "sml:gpu-waiter:{}"
AGENT_SLOTS, AGENT_WAITERS, AGENT_MODELS = "sml:agent-slots", "sml:agent-waiters", "sml:agent-models"
AGENT_QUEUES = {"sml.news", "sml.reasoning"}


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value


def _reservations(r: redis.Redis, key: str) -> list[int]:
    """Memory (MB) of each live reservation in a reservation table."""
    now, out = time.time(), []
    for raw in r.hvals(key):
        with contextlib.suppress(ValueError, TypeError, KeyError):
            entry = json.loads(raw)
            if entry["expires"] >= now:
                out.append(int(entry["mb"]))
    return out


def _waiting(r: redis.Redis, key: str) -> int:
    """Waiters still alive (a waiter refreshes its liveness key while it polls)."""
    members = [_text(m) for m in r.zrange(key, 0, -1)]
    return int(r.exists(*[WAITER_ALIVE.format(m) for m in members])) if members else 0


def _gpus(r: redis.Redis | None, workers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gpus: dict[tuple[str, str], dict[str, Any]] = {}
    for w in workers:
        gpu = str(w.get("gpu") or "")
        if not gpu:
            continue
        host = str(w.get("hostname", ""))
        entry = gpus.setdefault((host, gpu), {"host": host, "index": gpu, "workers": 0, "stats": w.get("gpu_stats"),
                                              "reserved_mb": 0, "running": 0, "waiting": 0})
        entry["workers"] += 1
        entry["stats"] = entry["stats"] or w.get("gpu_stats")
    if r is not None:
        for (host, gpu), entry in gpus.items():
            with contextlib.suppress(redis.RedisError):
                held = _reservations(r, GPU_RESERVATIONS.format(host=host, gpu=gpu))
                entry.update(reserved_mb=sum(held), running=len(held),
                             waiting=_waiting(r, GPU_WAITERS.format(host=host, gpu=gpu)))
    return sorted(gpus.values(), key=lambda g: (g["host"], g["index"]))


def _stream() -> dict[str, Any]:
    active = StreamSession.objects.filter(status=StreamSession.Status.RUNNING).count()
    try:
        resp = httpx.get(f"{settings.STREAM_INTERNAL_URL}/stream/health", timeout=3)
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError):
        return {"status": "error", "busy": False, "waiting": 0, "model_loaded": False, "gpu": None,
                "active_sessions": active}
    return {"status": "ok", "busy": bool(body.get("busy")), "waiting": int(body.get("waiting") or 0),
            "model_loaded": bool(body.get("model_loaded")), "gpu": body.get("gpu"), "active_sessions": active}


def _agents(r: redis.Redis | None, workers: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "error", "loaded": [], "running": 0, "waiting": 0,
                           "workers": sum(1 for w in workers if AGENT_QUEUES & set(w.get("queues", [])))}
    if r is not None:
        with contextlib.suppress(redis.RedisError):
            out.update(running=len(_reservations(r, AGENT_SLOTS)), waiting=_waiting(r, AGENT_WAITERS))
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/ps", timeout=3)
        resp.raise_for_status()
        models = resp.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return out
    out["status"] = "ok"
    out["loaded"] = [{"name": m.get("name") or m.get("model", ""),
                      "vram_mb": int((m.get("size_vram") or 0) / 1024 / 1024),
                      "context": m.get("context_length"),
                      "pinned": _pinned(str(m.get("expires_at", "")))}
                     for m in models]
    return out


def _pinned(expires_at: str) -> bool:
    """keep_alive -1 shows up as an expiry centuries away."""
    try:
        return int(expires_at[:4]) > datetime.now(UTC).year + 50
    except ValueError:
        return False


def _payment_mode(secret: str, test_prefixes: tuple[str, ...]) -> str:
    if not secret:
        return "off"
    return "test" if secret.startswith(test_prefixes) else "live"


def _configuration() -> dict[str, Any]:
    return {
        "debug": settings.DEBUG,
        "maintenance_mode": PlatformSettings.load().maintenance_mode,
        "email": "smtp" if "smtp" in settings.EMAIL_BACKEND else settings.EMAIL_BACKEND.rsplit(".", 2)[-2],
        "storage": "s3" if settings.S3_ENDPOINT_URL else "local",
        "captcha": bool(settings.TURNSTILE_SECRET_KEY),
        "toss": _payment_mode(settings.TOSS_SECRET_KEY, ("test_",)),
        "stripe": _payment_mode(settings.STRIPE_SECRET_KEY, ("sk_test_", "rk_test_")),
    }


def snapshot() -> dict[str, Any]:
    workers = live.workers()
    r = live.redis_or_none()
    return {
        "checked_at": time.time(),
        "checks": run_checks(ALL_CHECKS),
        "gpus": _gpus(r, workers),
        "stream": _stream(),
        "agents": _agents(r, workers),
        "workers": {"total": len(workers), "gpu": sum(1 for w in workers if w.get("gpu")),
                    "agents": sum(1 for w in workers if AGENT_QUEUES & set(w.get("queues", [])))},
        "configuration": _configuration(),
    }
