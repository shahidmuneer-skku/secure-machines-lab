"""GPU admission: a model starts only when its memory fits on this worker's GPU; others wait.

Every worker process on a host shares one reservation table per GPU in Redis. A task reserves
the memory its model needs, keeps the reservation alive while it runs, and releases it when it
ends (reservations of dead workers expire on their own). Admission counts both reservations and
memory used by anything else on the GPU (e.g. Ollama), so an under-declared model cannot push
the card out of memory. A task that has waited longer than AGING_SECONDS is served first, so
large models are not starved by a stream of small ones.

Memory needs: once a model has run on this media type, its observed peak plus HEADROOM; before
that, `gpu_mem_mb` from config/models.yaml. Both are capped below the card's size (a model that
needs more simply runs alone).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import redis

from .clients import redis_client
from .config import config

logger = logging.getLogger(__name__)

MARGIN_MB = int(os.environ.get("SML_GPU_MARGIN_MB", "1024"))
AGING_SECONDS = float(os.environ.get("SML_GPU_AGING_SECONDS", "120"))
# Driver/context memory an idle card reports; not counted as "used by other programs".
IDLE_BASELINE_MB = int(os.environ.get("SML_GPU_IDLE_BASELINE_MB", "512"))
# Declared or observed needs are capped below the card's usable size so an oversized declaration
# still runs (alone) instead of never fitting.
CAP_FRACTION = 0.95
HEADROOM = 1.25  # observed peaks vary between inputs
RESERVATION_TTL = 90.0
POLL_SECONDS = 2.0
PEAKS_KEY = "sml:gpu-model-peak"

_ACQUIRE = """
local key, waiters, needs = KEYS[1], KEYS[2], KEYS[3]
local task, need, capacity, now, ttl, aging = ARGV[1], tonumber(ARGV[2]), tonumber(ARGV[3]),
  tonumber(ARGV[4]), tonumber(ARGV[5]), tonumber(ARGV[6])
local reserved = 0
local entries = redis.call('HGETALL', key)
for i = 1, #entries, 2 do
  local v = cjson.decode(entries[i + 1])
  if v.expires < now then redis.call('HDEL', key, entries[i]) elseif entries[i] ~= task then
    reserved = reserved + v.mb end
end
-- The longest-waiting live task goes first once it has waited past the aging limit, but only if
-- it can actually fit (a task that cannot fit even on an idle card must not block the others).
local queue = redis.call('ZRANGE', waiters, 0, -1, 'WITHSCORES')
for i = 1, #queue, 2 do
  if redis.call('EXISTS', 'sml:gpu-waiter:' .. queue[i]) == 1 then
    local oldest_need = tonumber(redis.call('HGET', needs, queue[i]) or '0')
    if queue[i] ~= task and (now - tonumber(queue[i + 1])) > aging and oldest_need <= capacity then
      return {0, reserved}
    end
    break
  end
  redis.call('ZREM', waiters, queue[i])
  redis.call('HDEL', needs, queue[i])
end
if reserved + need > capacity then return {0, reserved} end
redis.call('HSET', key, task, cjson.encode({mb = need, expires = now + ttl}))
redis.call('ZREM', waiters, task)
redis.call('HDEL', needs, task)
return {1, reserved}
"""


def gpu_index() -> str:
    return os.environ.get("SML_WORKER_GPU") or os.environ.get("SML_WORKER_DEFAULT_GPU", "0")


def _nvidia_smi(*args: str) -> list[list[str]]:
    out = subprocess.run(["nvidia-smi", *args, "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=10, check=True).stdout
    return [[c.strip() for c in line.split(",")] for line in out.strip().splitlines() if line.strip()]


def memory(index: str) -> tuple[int, int]:
    """(total MB, used MB) of one GPU, indexed like nvidia-smi (PCI bus order)."""
    total, used = _nvidia_smi("--query-gpu=memory.total,memory.used", "-i", index)[0]
    return int(float(total)), int(float(used))


def _children(pid: int) -> list[int]:
    kids: list[int] = []
    for task in Path(f"/proc/{pid}/task").glob("*/children"):
        with contextlib.suppress(OSError):
            kids += [int(p) for p in task.read_text().split()]
    return kids


def process_tree_memory(root_pid: int) -> int:
    """GPU memory (MB) used by a process and all its descendants, on any GPU."""
    pids, stack = set(), [root_pid]
    while stack:
        pid = stack.pop()
        if pid not in pids:
            pids.add(pid)
            stack += _children(pid)
    try:
        rows = _nvidia_smi("--query-compute-apps=pid,used_memory")
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(int(float(mb)) for pid, mb in rows if pid.isdigit() and int(pid) in pids)


def need_mb(model_key: str, declared: int | None, total_mb: int) -> int:
    """Memory to reserve: the observed peak plus headroom once known, else the declaration (capped)."""
    cap = int((total_mb - MARGIN_MB) * CAP_FRACTION)
    with contextlib.suppress(redis.RedisError, ValueError, TypeError):
        observed = redis_client().hget(PEAKS_KEY, model_key)
        if observed:
            return min(max(512, int(float(observed) * HEADROOM)), cap)
    return min(int(declared or 0), cap) if declared else 0


def record_peak(model_key: str, peak_mb: int) -> None:
    """Remember the largest memory use seen for a model (used by need_mb next time)."""
    if peak_mb <= 0:
        return
    with contextlib.suppress(redis.RedisError):
        r = redis_client()
        current = int(float(r.hget(PEAKS_KEY, model_key) or 0))
        if peak_mb > current:
            r.hset(PEAKS_KEY, model_key, peak_mb)


class GpuTooSmall(Exception):
    pass


class Reservation:
    def __init__(self, key: str, task_id: str, mb: int):
        self.key, self.task_id, self.mb = key, task_id, mb
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._renew, daemon=True)
        self._thread.start()

    def _renew(self) -> None:
        while not self._stop.wait(RESERVATION_TTL / 3):
            with contextlib.suppress(redis.RedisError):
                redis_client().hset(self.key, self.task_id,
                                    json.dumps({"mb": self.mb, "expires": time.time() + RESERVATION_TTL}))

    def release(self) -> None:
        self._stop.set()
        with contextlib.suppress(redis.RedisError):
            redis_client().hdel(self.key, self.task_id)


@contextlib.contextmanager
def reserve(key: str, waiters: str, owner: str, need: int, capacity: Callable[[int], int],
            on_wait: Callable[[int, int], None], should_stop: Callable[[], None]) -> Iterator[None]:
    """Generic admission loop over a Redis reservation table.

    capacity(reserved_by_others) → how much may be reserved in total right now. Waits (calling
    on_wait(need, free) and should_stop()) until `need` fits, holds the reservation while the body
    runs and releases it afterwards.
    """
    r = redis_client()
    script = r.register_script(_ACQUIRE)
    start_key = f"sml:gpu-wait-start:{owner}"
    r.set(start_key, time.time(), nx=True, ex=3600)
    started = float(r.get(start_key) or time.time())
    r.zadd(waiters, {owner: started}, nx=True)
    needs = f"{waiters}:needs"
    r.hset(needs, owner, need)
    reservation = None
    try:
        while True:
            r.set(f"sml:gpu-waiter:{owner}", 1, ex=max(5, int(POLL_SECONDS * 5)))
            reserved_now = sum(json.loads(v)["mb"] for k, v in r.hgetall(key).items()
                               if (k.decode() if isinstance(k, bytes) else k) != owner)
            limit = capacity(reserved_now)
            ok, reserved = script(keys=[key, waiters, needs],
                                  args=[owner, need, limit, time.time(), RESERVATION_TTL, AGING_SECONDS])
            if ok:
                reservation = Reservation(key, owner, need)
                break
            on_wait(need, max(0, limit - int(reserved)))
            should_stop()
            time.sleep(POLL_SECONDS)
        r.delete(start_key, f"sml:gpu-waiter:{owner}")
        yield
    finally:
        with contextlib.suppress(redis.RedisError):
            r.zrem(waiters, owner)
            r.hdel(needs, owner)
            r.delete(start_key, f"sml:gpu-waiter:{owner}")
        if reservation is not None:
            reservation.release()


@contextlib.contextmanager
def admitted(task_id: str, need: int, on_wait: Callable[[int, int], None],
             should_stop: Callable[[], None] = lambda: None) -> Iterator[None]:
    """Block until `need` MB fit on this worker's GPU and hold them while the body runs.

    Without Redis or nvidia-smi the task runs unadmitted (admission never blocks processing).
    """
    if need <= 0:
        yield
        return
    index = gpu_index()
    host = config().hostname
    try:
        total, _ = memory(index)
        redis_client().ping()
    except (redis.RedisError, OSError, subprocess.SubprocessError, IndexError, ValueError):
        logger.warning("GPU admission unavailable; running %s without it", task_id, exc_info=True)
        yield
        return
    if need > total - MARGIN_MB:
        raise GpuTooSmall(f"needs {need} MB, GPU {index} has {total} MB")

    def capacity(reserved_by_others: int) -> int:
        total_mb, used = memory(index)
        # Memory used by processes without a reservation (other programs), above the idle baseline.
        external = max(0, used - reserved_by_others - IDLE_BASELINE_MB)
        return total_mb - MARGIN_MB - external

    with reserve(f"sml:gpu-reservations:{host}:{index}", f"sml:gpu-waiters:{host}:{index}", task_id, need,
                 capacity, on_wait, should_stop):
        yield
