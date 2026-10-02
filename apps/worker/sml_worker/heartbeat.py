"""Publishes worker presence (queues, GPU, current task, GPU stats) to Redis every few seconds."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any

from .clients import redis_client
from .config import config
from .runner import current_task

logger = logging.getLogger(__name__)
KEY = "sml:worker:{}"


def gpu_stats(gpu: str) -> dict[str, Any] | None:
    if gpu in ("", None):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--id={gpu}", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        name, util, used, total, temp = [x.strip() for x in out.split(",")]
        return {"name": name, "util": int(util), "mem_used_mb": int(used), "mem_total_mb": int(total),
                "temp_c": int(temp)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


class Heartbeat(threading.Thread):
    daemon = True

    def __init__(self, queues: list[str], gpu: str, interval: float = 10.0):
        super().__init__(name="sml-heartbeat")
        self.queues = queues
        self.gpu = gpu
        self.interval = interval
        self.worker_id = f"{config().hostname}-{os.getpid()}"
        self.started = datetime.now(timezone.utc).isoformat()
        self._stop_event = threading.Event()

    def beat(self) -> None:
        payload = {"id": self.worker_id, "hostname": config().hostname, "pid": os.getpid(), "gpu": self.gpu,
                   "queues": self.queues, "started_at": self.started, "current_task": dict(current_task) or None,
                   "gpu_stats": gpu_stats(self.gpu), "simulate": config().simulate,
                   "updated_at": datetime.now(timezone.utc).isoformat()}
        try:
            redis_client().set(KEY.format(self.worker_id), json.dumps(payload), ex=int(self.interval * 3))
        except Exception:
            logger.debug("heartbeat failed", exc_info=True)

    def run(self) -> None:
        while not self._stop_event.wait(self.interval):
            self.beat()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            redis_client().delete(KEY.format(self.worker_id))
        except Exception:
            logger.debug("Could not remove heartbeat key", exc_info=True)
