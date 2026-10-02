"""Executes one task envelope: chooses the adapter, reports events, uploads artifacts."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import time
import traceback
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis

from . import gpu as gpu_admission
from .adapters.audit import AuditAdapter, SimulatedAuditAdapter
from .adapters.base import AdapterError, ModelResult
from .adapters.long_video import LongVideoAdapter, SimulatedLongVideoAdapter
from .adapters.metadata import MetadataAdapter
from .adapters.simulated import SimulatedAdapter
from .adapters.subprocess_cli import SubprocessAdapter
from .clients import download, redis_client
from .config import config
from .context import RESULT_KEY, RESULT_TTL_SECONDS, Canceled, TaskContext
from .registry import audit_spec, long_video_spec, model_spec, raw_registry
from .resident import supervisor as resident

logger = logging.getLogger(__name__)
RESULT_TASK = "sml.jobs.record_task_event"
EXPLAIN_RESULT_TASK = "sml.jobs.record_explanation_event"
RESULTS_QUEUE = "sml.results"
current_task: dict[str, Any] = {}


def _simulate(available: bool) -> bool:
    mode = config().simulate
    if mode == "1":
        return True
    if mode == "0":
        return False
    return not available


def _adapter(envelope: dict[str, Any]) -> Any:
    kind, target, media_type = envelope["kind"], envelope["target"], envelope.get("media_type", "")
    if kind == "model":
        spec = model_spec(target)
        if spec is None or media_type not in (spec.get("media") or {}):
            raise AdapterError("CONFIG_ERROR", f"Model {target} does not support {media_type}.")
        media_spec = spec["media"][media_type]
        timeout = int(media_spec.get("timeout_seconds", 300))
        real = SubprocessAdapter(spec, media_spec, timeout)
        return SimulatedAdapter(spec) if _simulate(real.available()) else real
    if kind == "audit":
        if target == "metadata":
            return MetadataAdapter()
        spec = audit_spec(target)
        if spec is None:
            raise AdapterError("CONFIG_ERROR", f"Unknown audit step {target}.")
        real = AuditAdapter(spec)
        return SimulatedAuditAdapter(spec) if _simulate(real.available()) else real
    if kind == "long_video":
        spec = long_video_spec(target)
        if spec is None:
            raise AdapterError("CONFIG_ERROR", f"Unknown long-video model {target}.")
        real = LongVideoAdapter(spec)
        return SimulatedLongVideoAdapter(spec) if _simulate(real.available()) else real
    raise AdapterError("CONFIG_ERROR", f"Unsupported task kind {kind}.")


def _send(app: Any, name: str, payload: dict[str, Any]) -> None:
    if name == RESULT_TASK and payload.get("event") == "finished":
        keep_result(payload)
    app.send_task(name, args=[payload], queue=RESULTS_QUEUE, routing_key=RESULTS_QUEUE, priority=9)


def keep_result(payload: dict[str, Any]) -> None:
    """Keep the final result in Redis too: if the API loses the message (a restart mid-deploy, a
    database error), its stale-task sweep replays it instead of re-running the model."""
    with contextlib.suppress(redis.RedisError):
        redis_client().set(RESULT_KEY.format(payload["task_id"]), json.dumps({**payload, "kept_at": _now()}),
                           ex=RESULT_TTL_SECONDS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def already_finished(task_id: str, attempt: int) -> bool:
    """True when this attempt's final result is already kept, i.e. this delivery is a duplicate.

    RabbitMQ delivers at least once: when a channel closes (e.g. a delivery-acknowledgement timeout)
    every message the worker held goes back to the queue, including ones another pool process is
    still finishing. Running them again would only repeat the model on the GPU.
    """
    try:
        raw = redis_client().get(RESULT_KEY.format(task_id))
    except redis.RedisError:
        return False
    if not raw:
        return False
    with contextlib.suppress(ValueError, TypeError, AttributeError):
        return int(json.loads(raw).get("attempt", 0)) == int(attempt)
    return False


def run_envelope(app: Any, envelope: dict[str, Any]) -> None:
    if envelope.get("kind") == "explain":
        return run_explain(app, envelope)
    task_id = envelope["task_id"]
    if already_finished(task_id, envelope.get("attempt", 1)):
        logger.info("Task %s (attempt %s) already finished; skipping a duplicate delivery", task_id,
                    envelope.get("attempt", 1))
        return None
    gpu = os.environ.get("SML_WORKER_GPU", "")
    base = {"task_id": task_id, "attempt": envelope.get("attempt", 1)}
    workdir = config().scratch_root / task_id
    workdir.mkdir(parents=True, exist_ok=True)
    ctx = TaskContext(envelope, workdir, gpu)
    current_task.update({"task_id": task_id, "job_id": envelope.get("job_id"), "target": envelope.get("target"),
                         "started": _now()})
    started = time.monotonic()
    try:
        if ctx.canceled():
            raise Canceled()
        # Detectors start only when their GPU memory fits; until then the task stays queued.
        with _admission(task_id, envelope, ctx):
            started = time.monotonic()
            _send(app, RESULT_TASK, {**base, "event": "started", "worker": f"{config().hostname}:{os.getpid()}",
                                     "gpu": gpu, "at": _now()})
            if envelope["kind"] == "news":
                result = _run_news(envelope, ctx)
            elif envelope["kind"] == "studio":
                from .studio.task import run_studio

                result = run_studio(envelope, ctx)
            else:
                media = envelope.get("media") or {}
                local = download(media["storage_key"], workdir / f"source.{media.get('extension', 'bin')}")
                ctx.progress(2, "File downloaded", force=True)
                adapter = _adapter(envelope)
                result = adapter.run(local, envelope.get("media_type", ""), ctx)
        ctx.progress(100, "Done", force=True)
        _send(app, RESULT_TASK, {**base, "event": "finished", "status": "succeeded",
                                 "result": result.as_dict(), "artifacts": [a.as_dict() for a in ctx.artifacts],
                                 "duration_ms": int((time.monotonic() - started) * 1000)})
    except Canceled:
        ctx.log("Canceled by user")
        _send(app, RESULT_TASK, {**base, "event": "finished", "status": "canceled",
                                 "duration_ms": int((time.monotonic() - started) * 1000)})
    except gpu_admission.GpuTooSmall as exc:
        logger.warning("Task %s cannot run on GPU %s: %s", task_id, gpu, exc)
        ctx.log("Failed (GPU_UNSUPPORTED)")
        _send(app, RESULT_TASK, {**base, "event": "finished", "status": "failed", "error_code": "GPU_UNSUPPORTED",
                                 "error_message": f"Not enough GPU memory on this worker: {exc}"})
    except AdapterError as exc:
        # The technical message goes to the API for staff; users see only the classified code.
        logger.warning("Task %s failed (%s): %s", task_id, exc.code, exc.message)
        ctx.log(f"Failed ({exc.code})")
        _send(app, RESULT_TASK, {**base, "event": "finished", "status": "failed", "error_code": exc.code,
                                 "error_message": exc.message, "artifacts": [a.as_dict() for a in ctx.artifacts],
                                 "duration_ms": int((time.monotonic() - started) * 1000)})
    except Exception as exc:  # noqa: BLE001 - report infrastructure failures, never crash the worker
        logger.error("Task %s crashed: %s", task_id, traceback.format_exc())
        _send(app, RESULT_TASK, {**base, "event": "finished", "status": "failed", "error_code": "INFRA_ERROR",
                                 "error_message": f"{type(exc).__name__}: {str(exc)[:200]}",
                                 "duration_ms": int((time.monotonic() - started) * 1000)})
    finally:
        current_task.clear()
        shutil.rmtree(workdir, ignore_errors=True)


# How long a task waits for its model's resident server to finish loading before it loads the model itself.
RESIDENT_LOAD_WAIT_SECONDS = 900


def _await_resident(envelope: dict[str, Any], ctx: TaskContext) -> None:
    """While the model's resident server is still loading, wait for it instead of loading a second copy
    next to it: two copies of a large model (SKKU-P2, 14 GB) do not fit on one GPU, and the task would
    fail with GPU_OOM. A server that is down, or still loading after the limit, does not hold the task."""
    if envelope.get("kind") != "model":
        return
    target, media_type = envelope.get("target", ""), envelope.get("media_type", "")
    deadline = time.monotonic() + RESIDENT_LOAD_WAIT_SECONDS
    announced = False
    while resident.loading_servers(target, media_type) and not resident.ready_servers(target, media_type):
        if time.monotonic() > deadline:
            ctx.log("The model's resident server is still loading; loading the model for this task")
            return
        if not announced:
            ctx.log("Waiting for the model's resident server to finish loading")
            announced = True
        ctx.progress(0, "Waiting for the model to load")
        ctx.check_canceled()
        time.sleep(2)


class _ResidentReady(Exception):
    """A task waiting for GPU memory can run on its model's resident server instead."""


@contextlib.contextmanager
def _admission(task_id: str, envelope: dict[str, Any], ctx: TaskContext) -> Iterator[None]:
    """Hold the GPU memory the task needs while it runs. A task that arrived before its model's resident
    server was ready waits for memory to load the model itself; once the server is ready it stops
    waiting and runs there (needing no memory of its own)."""
    _await_resident(envelope, ctx)
    with contextlib.ExitStack() as stack:
        while True:
            need = _gpu_need(envelope)

            def should_stop(need: int = need) -> None:
                ctx.check_canceled()
                if need and envelope.get("kind") == "model" and resident.ready_servers(
                        envelope.get("target", ""), envelope.get("media_type", "")):
                    raise _ResidentReady()

            try:
                stack.enter_context(gpu_admission.admitted(
                    task_id, need, on_wait=lambda need, free: _waiting(ctx, need, free), should_stop=should_stop))
                break
            except _ResidentReady:
                ctx.log("The model's resident server is ready; running there")
        yield


def _gpu_need(envelope: dict[str, Any]) -> int:
    """GPU memory (MB) a task must reserve before it starts; 0 for work that needs no GPU slot."""
    kind, target = envelope.get("kind"), envelope.get("target", "")
    if kind == "model" and resident.ready_servers(target, envelope.get("media_type", "")):
        return 0  # its resident server already holds the memory
    if kind == "model":
        spec = model_spec(target) or {}
    elif kind == "audit" and target != "metadata":
        spec = audit_spec(target) or {}
    elif kind == "long_video":
        spec = long_video_spec(target) or {}
    else:
        return 0  # metadata runs on CPU; agents are admitted by agents/ollama.py; the studio server by itself
    declared = spec.get("gpu_mem_mb") or raw_registry().get("defaults", {}).get("gpu_mem_mb", 6000)
    try:
        total, _ = gpu_admission.memory(gpu_admission.gpu_index())
    except Exception:  # noqa: BLE001 - no nvidia-smi: admission is skipped anyway
        return 0
    return gpu_admission.need_mb(f"{kind}:{target}:{envelope.get('media_type', '')}", int(declared), total)


def _waiting(ctx: TaskContext, need: int, free: int) -> None:
    ctx.progress(0, f"Waiting for GPU memory: needs {need / 1024:.1f} GB, {free / 1024:.1f} GB free")


def _run_news(envelope: dict[str, Any], ctx: TaskContext) -> ModelResult:
    from .agents.engine import EngineError
    from .agents.news import run_news

    case = envelope.get("news_case") or {}
    try:
        out = run_news(envelope, case.get("input") or {}, case.get("media") or [], ctx)
    except EngineError as exc:
        raise AdapterError("AGENT_ERROR", str(exc)) from exc
    return ModelResult(extra=out)


def run_explain(app: Any, envelope: dict[str, Any]) -> None:
    from .agents.engine import EngineError
    from .agents.explain import run_explanation

    exp_id = envelope["explanation_id"]
    workdir = config().scratch_root / f"explain-{exp_id}"
    workdir.mkdir(parents=True, exist_ok=True)
    ctx = TaskContext(envelope, workdir, os.environ.get("SML_WORKER_GPU", ""))
    ctx.task_id = exp_id
    base = {"explanation_id": exp_id}
    _send(app, EXPLAIN_RESULT_TASK, {**base, "event": "started"})
    original_log = ctx.log

    def log_and_forward(message: str) -> None:
        original_log(message)
        _send(app, EXPLAIN_RESULT_TASK, {**base, "event": "progress", "message": message[:300]})

    ctx.log = log_and_forward  # type: ignore[method-assign]
    try:
        content = run_explanation(envelope, ctx)
        if not content:
            raise EngineError("The reasoning agent returned an empty answer.")
        _send(app, EXPLAIN_RESULT_TASK, {**base, "event": "finished", "status": "succeeded", "content": content})
    except (EngineError, Canceled, Exception) as exc:  # noqa: BLE001
        logger.warning("Explanation %s failed: %s", exp_id, exc)
        _send(app, EXPLAIN_RESULT_TASK, {**base, "event": "finished", "status": "failed",
                                         "error_message": str(exc)[:300] or type(exc).__name__})
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def ensure_scratch() -> Path:
    root = config().scratch_root
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root
