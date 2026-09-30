"""Long-form video scanner: streams per-interval scores from the long-video engine."""

from __future__ import annotations

import ast
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from ..config import config, gpu_env
from ..context import Canceled, TaskContext
from .base import AdapterError, ModelResult


def _event(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    for loader in (json.loads, ast.literal_eval):
        try:
            value = loader(line)
            return value if isinstance(value, dict) else None
        except (ValueError, SyntaxError):
            continue
    return None


class LongVideoAdapter:
    def __init__(self, spec: dict[str, Any]):
        self.id = spec["id"]
        self.spec = spec

    def available(self) -> bool:
        return config().conda_python(self.spec.get("conda_env", "")).exists()

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        c = config()
        interval = float((ctx.envelope.get("options") or {}).get("interval_seconds", 5))
        duration = float((ctx.envelope.get("media") or {}).get("duration_seconds") or 0)
        expected = max(1, math.ceil(duration / interval)) if duration else None
        values = {"python": str(c.conda_python(self.spec.get("conda_env", ""))), "input": str(media_path),
                  "interval": f"{interval:g}", "long_video_root": str(c.long_video_root)}
        argv = [str(p).format(**values) for p in self.spec["argv"]]
        cwd = str(self.spec.get("cwd", "{long_video_root}")).format(long_video_root=c.long_video_root)
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        env.update(gpu_env())
        ctx.log(f"Scanning long video in {interval:g}s intervals"
                + (f" (~{expected} intervals)" if expected else ""))
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        intervals: list[dict[str, Any]] = []
        done: dict[str, Any] | None = None
        deadline = time.monotonic() + int(self.spec.get("timeout_seconds", 14400))
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if time.monotonic() > deadline:
                    raise AdapterError("TIMEOUT", "Long-video scan timed out.")
                ev = _event(line)
                if not ev:
                    continue
                if ev.get("type") == "interval":
                    item = {"index": ev.get("index"), "start_sec": ev.get("start_sec"), "end_sec": ev.get("end_sec"),
                            "fake_prob": ev.get("fake_probability")}
                    intervals.append(item)
                    pct = 100 * len(intervals) / expected if expected else min(95, len(intervals))
                    ctx.progress(min(95, pct), f"Interval {len(intervals)}"
                                 + (f"/{expected}" if expected else "")
                                 + f": {float(item['fake_prob'] or 0) * 100:.0f}% fake")
                    ctx._publish("task.interval", {"job_id": ctx.job_id, "task_id": ctx.task_id, "interval": item})
                elif ev.get("type") == "done":
                    done = ev
        except Canceled:
            os.killpg(proc.pid, signal.SIGTERM)
            raise
        proc.wait(timeout=30)
        if proc.returncode != 0 and done is None:
            err = (proc.stderr.read() if proc.stderr else "").strip().splitlines()
            raise AdapterError("RUNTIME_ERROR", (err or ["Long-video engine failed"])[-1][:300])
        if done is None:
            raise AdapterError("PARSE_ERROR", "The long-video engine produced no final verdict.")
        return ModelResult(fake_prob=float(done.get("average_fake_probability", 0)), intervals=intervals,
                           extra={"processing_time_sec": done.get("processing_time_sec"),
                                  "effective_fps": done.get("effective_processing_fps")})


class SimulatedLongVideoAdapter:
    def __init__(self, spec: dict[str, Any]):
        self.id = spec["id"]

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        import hashlib

        interval = float((ctx.envelope.get("options") or {}).get("interval_seconds", 5))
        duration = float((ctx.envelope.get("media") or {}).get("duration_seconds") or 60)
        n = max(1, min(120, math.ceil(duration / interval)))
        seed = int(hashlib.sha256(str(ctx.envelope.get("media", {}).get("sha256", "")).encode()).hexdigest()[:8], 16)
        ctx.log(f"[simulated] long-form scan, {n} intervals")
        intervals = []
        for i in range(n):
            prob = 0.5 + 0.45 * math.sin((i + seed % 17) / 3.0) * math.cos(seed % 7 + i / 11)
            item = {"index": i, "start_sec": i * interval, "end_sec": min(duration, (i + 1) * interval),
                    "fake_prob": round(max(0.0, min(1.0, prob)), 4)}
            intervals.append(item)
            ctx.progress(95 * (i + 1) / n, f"Interval {i + 1}/{n}")
            ctx._publish("task.interval", {"job_id": ctx.job_id, "task_id": ctx.task_id, "interval": item})
            time.sleep(0.15)
        avg = sum(i["fake_prob"] for i in intervals) / len(intervals)
        return ModelResult(fake_prob=round(avg, 6), intervals=intervals, simulated=True)
