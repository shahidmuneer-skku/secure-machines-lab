"""Starts and watches the resident model servers (`python -m sml_worker --resident`).

Every model in config/models.yaml with a `resident` block gets one server per listed script, run with
the model's conda Python on the block's GPU (sml_worker/resident/server.py). The supervisor restarts a
server that exits (with back-off) and publishes each server's state in Redis; detector workers route a
task through a server only while it is "ready" and otherwise load the model per task as before.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import redis

from ..clients import redis_client
from ..config import REPO_ROOT, config
from ..procenv import model_env
from ..registry import raw_registry

logger = logging.getLogger(__name__)

HOOK_DIR = Path(__file__).resolve().parent / "hook"
SERVER_PY = Path(__file__).resolve().parent / "server.py"
STATUS_KEY = "sml:resident:{}"
STATUS_TTL = 30
WARMUP_STEM = "sml-resident-warmup"


def resident_dir() -> Path:
    return Path(os.environ.get("SML_RESIDENT_DIR") or REPO_ROOT / "var" / "run" / "resident")


@dataclass
class ServerSpec:
    id: str
    model_id: str
    media: list[str]
    script: str
    conda_env: str
    gpu: str
    mode: str = "run"
    cache: list[str] = field(default_factory=list)
    warmup: list[list[str]] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    torch_load_cache: bool = False
    max_run_seconds: int = 0

    @property
    def socket(self) -> str:
        return str(resident_dir() / f"{self.id}.sock")


def _fill(value: str) -> str:
    c = config()
    return value.format(models_root=c.models_root, warmup_image=c.models_root / "iu.png",
                        warmup_image_dir=resident_dir() / "warmup" / "images",  # a folder holding that image
                        warmup_dir=resident_dir() / "warmup", stem=WARMUP_STEM)


def servers() -> list[ServerSpec]:
    out = []
    for model in raw_registry().get("models", []):
        block = model.get("resident")
        if not block:
            continue
        for index, srv in enumerate(block.get("servers", [])):
            media = list(srv.get("media") or model.get("media", {}).keys())
            env_name = srv.get("conda_env") or next(
                (model["media"][m].get("conda_env") for m in media if m in model.get("media", {})), "")
            out.append(ServerSpec(
                id=srv.get("id") or (model["id"] if len(block["servers"]) == 1 else f"{model['id']}-{index + 1}"),
                model_id=model["id"], media=media, script=os.path.realpath(_fill(srv["script"])),
                conda_env=env_name, gpu=str(srv.get("gpu", block.get("gpu", 0))), mode=srv.get("mode", "run"),
                cache=list(srv.get("cache", [])), warmup=[[_fill(a) for a in argv] for argv in srv.get("warmup", [])],
                env={k: _fill(str(v)) for k, v in (srv.get("env") or {}).items()},
                torch_load_cache=bool(srv.get("torch_load_cache", False)),
                # the model's own time limit, plus slack for the wrapper's steps around the run
                max_run_seconds=120 + max(int(model["media"][m].get(
                    "timeout_seconds", raw_registry().get("defaults", {}).get("timeout_seconds", 300)))
                    for m in media if m in model.get("media", {})),
            ))
    return out


# --- what detector workers use --------------------------------------------------------------------

def ready_servers(model_id: str, media_type: str) -> list[ServerSpec]:
    """Servers of this model and media type that report ready and have their socket in place."""
    candidates = [s for s in servers() if s.model_id == model_id and media_type in s.media]
    if not candidates:
        return []
    try:
        states = redis_client().mget([STATUS_KEY.format(s.id) for s in candidates])
    except redis.RedisError:
        return []
    ready = []
    for spec, raw in zip(candidates, states, strict=True):
        status = json.loads(raw) if raw else {}
        if status.get("state") == "ready" and Path(spec.socket).exists():
            ready.append(spec)
    return ready


def routing_env(model_id: str, media_type: str) -> dict[str, str]:
    """Environment that sends launches of this model's resident scripts to their servers."""
    ready = ready_servers(model_id, media_type)
    if not ready:
        return {}
    return {"PYTHONPATH": str(HOOK_DIR), "SML_RESIDENT": json.dumps({s.script: s.socket for s in ready})}


# --- supervisor -----------------------------------------------------------------------------------

@dataclass
class Running:
    spec: ServerSpec
    proc: subprocess.Popen | None = None
    started: float = 0.0
    ready_at: float | None = None
    restarts: int = 0
    next_start: float = 0.0


def _start(run: Running) -> None:
    spec, c = run.spec, config()
    images = resident_dir() / "warmup" / "images"
    images.mkdir(parents=True, exist_ok=True)
    if not (images / "warmup.png").exists() and (c.models_root / "iu.png").exists():
        (images / "warmup.png").symlink_to(c.models_root / "iu.png")
    cfg_path = resident_dir() / f"{spec.id}.json"
    cfg_path.write_text(json.dumps({
        "socket": spec.socket, "script": spec.script, "mode": spec.mode, "cache": spec.cache,
        "cwd": os.path.dirname(spec.script), "torch_load_cache": spec.torch_load_cache,
        "max_run_seconds": spec.max_run_seconds,
        "warmup": [{"argv": argv, "cwd": str(c.models_root)} for argv in spec.warmup],
    }))
    env = model_env(spec.conda_env)
    env.update({"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": spec.gpu, **spec.env})
    log_path = REPO_ROOT / "var" / "log" / f"resident-{spec.id}.log"
    with contextlib.suppress(FileNotFoundError):
        os.unlink(spec.socket)
    log_file = log_path.open("ab")
    run.proc = subprocess.Popen([str(c.conda_python(spec.conda_env)), str(SERVER_PY), "--config", str(cfg_path)],
                                cwd=os.path.dirname(spec.script), env=env, stdout=log_file, stderr=log_file,
                                start_new_session=True)
    log_file.close()
    run.started, run.ready_at = time.time(), None
    logger.info("Started resident server %s (pid %s, GPU %s, log %s)", spec.id, run.proc.pid, spec.gpu, log_path)


def _cleanup_warmup_outputs() -> None:
    root = config().models_root
    for sub in ("inference_images", "inference_csv", "detected"):
        for path in (root / sub).glob(f"{WARMUP_STEM}*"):
            with contextlib.suppress(OSError):
                path.unlink()


def _publish(run: Running, state: str) -> None:
    status = {"state": state, "model": run.spec.model_id, "media": run.spec.media, "gpu": run.spec.gpu,
              "pid": run.proc.pid if run.proc else None, "started_at": run.started, "ready_at": run.ready_at,
              "restarts": run.restarts, "script": run.spec.script}
    with contextlib.suppress(redis.RedisError):
        redis_client().set(STATUS_KEY.format(run.spec.id), json.dumps(status), ex=STATUS_TTL)


def supervise(only: list[str] | None = None) -> None:
    specs = [s for s in servers() if not only or s.id in only or s.model_id in only]
    if not specs:
        logger.warning("No resident servers configured (models.yaml `resident` blocks)")
        return
    runs = [Running(spec) for spec in specs]
    stopping = False

    def stop(*_: Any) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping:
            now = time.time()
            for run in runs:
                if run.proc is None or run.proc.poll() is not None:
                    if run.proc is not None:
                        logger.warning("Resident server %s exited with %s", run.spec.id, run.proc.returncode)
                        run.restarts += 1
                        run.next_start = now + min(300, 10 * 2 ** min(run.restarts, 5))
                        run.proc = None
                    if now >= run.next_start:
                        _start(run)
                    _publish(run, "down" if run.proc is None else "loading")
                    continue
                if run.ready_at is None and Path(run.spec.socket).exists():
                    run.ready_at = now
                    _cleanup_warmup_outputs()
                    logger.info("Resident server %s ready after %.0fs", run.spec.id, now - run.started)
                _publish(run, "ready" if run.ready_at else "loading")
            time.sleep(5)
    finally:
        for run in runs:
            if run.proc is not None and run.proc.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(run.proc.pid, signal.SIGTERM)
        deadline = time.time() + 30
        for run in runs:
            if run.proc is not None:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    run.proc.wait(timeout=max(0.1, deadline - time.time()))
                if run.proc.poll() is None:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(run.proc.pid, signal.SIGKILL)
            with contextlib.suppress(redis.RedisError):
                redis_client().delete(STATUS_KEY.format(run.spec.id))
