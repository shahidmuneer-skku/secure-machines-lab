"""Executes one task envelope: chooses the adapter, reports events, uploads artifacts."""

from __future__ import annotations

import logging
import os
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters.audit import AuditAdapter, SimulatedAuditAdapter
from .adapters.base import AdapterError, ModelResult
from .adapters.long_video import LongVideoAdapter, SimulatedLongVideoAdapter
from .adapters.metadata import MetadataAdapter
from .adapters.simulated import SimulatedAdapter
from .adapters.subprocess_cli import SubprocessAdapter
from .clients import download
from .config import config
from .context import Canceled, TaskContext
from .registry import audit_spec, long_video_spec, model_spec

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
    app.send_task(name, args=[payload], queue=RESULTS_QUEUE, routing_key=RESULTS_QUEUE, priority=9)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_envelope(app: Any, envelope: dict[str, Any]) -> None:
    if envelope.get("kind") == "explain":
        return run_explain(app, envelope)
    task_id = envelope["task_id"]
    gpu = os.environ.get("SML_WORKER_GPU", "")
    base = {"task_id": task_id, "attempt": envelope.get("attempt", 1)}
    workdir = config().scratch_root / task_id
    workdir.mkdir(parents=True, exist_ok=True)
    ctx = TaskContext(envelope, workdir, gpu)
    current_task.update({"task_id": task_id, "job_id": envelope.get("job_id"), "target": envelope.get("target"),
                         "started": _now()})
    started = time.monotonic()
    _send(app, RESULT_TASK, {**base, "event": "started", "worker": f"{config().hostname}:{os.getpid()}",
                             "gpu": gpu, "at": _now()})
    try:
        if ctx.canceled():
            raise Canceled()
        if envelope["kind"] == "news":
            result = _run_news(envelope, ctx)
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
    except AdapterError as exc:
        ctx.log(f"Failed: {exc.message}")
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
