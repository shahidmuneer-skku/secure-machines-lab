"""Audit-chain steps (face detection, content safety, face anti-spoofing) via their JSON-emitting scripts."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ..config import config, gpu_env
from ..context import TaskContext
from .base import AdapterError, ModelResult


def _last_json(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def summarize(step: str, data: dict[str, Any]) -> str:
    if step == "face":
        faces = data.get("faces") or data.get("face_count") or data.get("num_faces")
        count = len(faces) if isinstance(faces, list) else faces
        return f"{count} face(s) detected" if count is not None else "Face detection completed"
    if step == "safety":
        nsfw = (data.get("nsfw") or {}).get("confidence")
        return f"NSFW confidence {float(nsfw) * 100:.1f}%" if nsfw is not None else "Content safety checked"
    if step == "fas":
        label = data.get("label") or data.get("result") or data.get("prediction")
        return f"Anti-spoofing: {label}" if label else "Anti-spoofing completed"
    return "Completed"


class AuditAdapter:
    def __init__(self, step: dict[str, Any]):
        self.id = step["id"]
        self.step = step

    def available(self) -> bool:
        return config().conda_python(self.step.get("conda_env", "")).exists()

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        c = config()
        template = self.step.get("video_argv") if media_type == "video" and self.step.get("video_argv") \
            else self.step["argv"]
        values = {"python": str(c.conda_python(self.step.get("conda_env", ""))), "input": str(media_path),
                  "models_root": str(c.models_root)}
        argv = [str(p).format(**values) for p in template]
        cwd = str(self.step.get("cwd", "{models_root}")).format(models_root=c.models_root)
        env = dict(os.environ)
        env.update(gpu_env())
        ctx.log(f"Running audit step: {self.step.get('display_name', {}).get('en', self.id)}")
        ctx.progress(10, "Running", force=True)
        start = time.monotonic()
        try:
            proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                                  timeout=int(self.step.get("timeout_seconds", 600)), check=False)
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("TIMEOUT", "Audit step timed out.") from exc
        data = _last_json(proc.stdout)
        if proc.returncode != 0 and data is None:
            if self.id == "face" and ("No faces" in proc.stderr or "얼굴" in proc.stderr):
                return ModelResult(extra={"faces": [], "summary": "No face detected"})
            raise AdapterError("RUNTIME_ERROR", (proc.stderr.strip().splitlines() or ["failed"])[-1][:300])
        data = data or {}
        ctx.log(f"Audit step finished in {time.monotonic() - start:.1f}s")
        return ModelResult(extra={"data": data, "summary": summarize(self.id, data)})


class SimulatedAuditAdapter:
    def __init__(self, step: dict[str, Any]):
        self.id = step["id"]

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        ctx.log(f"[simulated] audit step {self.id}")
        for i in range(5):
            ctx.progress(20 * i, "Running")
            time.sleep(0.4)
        canned = {"face": {"faces": [{"bbox": [0.3, 0.2, 0.4, 0.5], "score": 0.99}]},
                  "safety": {"nsfw": {"confidence": 0.02}, "sfw": {"confidence": 0.98}},
                  "fas": {"label": "live", "score": 0.93}}.get(self.id, {})
        return ModelResult(simulated=True, extra={"data": canned, "summary": summarize(self.id, canned)})
