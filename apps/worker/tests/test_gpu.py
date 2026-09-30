"""GPU admission against a real Redis (Lua); skipped when Redis is not reachable."""

from __future__ import annotations

import threading
import time
import uuid
from types import SimpleNamespace

import pytest

from sml_worker import gpu


@pytest.fixture
def redis_ok():
    from sml_worker.clients import redis_client

    try:
        redis_client().ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Redis not reachable")
    return redis_client()


@pytest.fixture
def fake_gpu(monkeypatch, redis_ok):  # type: ignore[no-untyped-def]
    state = {"total": 24000, "external": 0}
    host = f"test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(gpu, "config", lambda: SimpleNamespace(hostname=host))
    monkeypatch.setattr(gpu, "POLL_SECONDS", 0.05)

    def memory(index):  # type: ignore[no-untyped-def]
        reserved = sum(int(__import__("json").loads(v)["mb"]) for v in
                       redis_ok.hvals(f"sml:gpu-reservations:{host}:{index}"))
        return state["total"], reserved + state["external"]

    monkeypatch.setattr(gpu, "memory", memory)
    yield state
    for key in redis_ok.keys(f"sml:gpu-*{host}*"):
        redis_ok.delete(key)


def run_admitted(task, need, log, hold=0.3):  # type: ignore[no-untyped-def]
    with gpu.admitted(task, need, on_wait=lambda n, f: None):
        log.append(("start", task, time.monotonic()))
        time.sleep(hold)
        log.append(("end", task, time.monotonic()))


def test_tasks_run_together_while_memory_fits_and_the_rest_wait(fake_gpu):
    log: list = []
    threads = [threading.Thread(target=run_admitted, args=(f"t{i}", 10000, log)) for i in range(3)]
    for t in threads:
        t.start()
        time.sleep(0.02)
    for t in threads:
        t.join(10)
    starts = {task: at for kind, task, at in log if kind == "start"}
    ends = {task: at for kind, task, at in log if kind == "end"}
    assert len(starts) == 3
    # 24000 - 1024 margin fits two 10 GB models: the third starts only after one finished.
    assert starts["t2"] >= min(ends["t0"], ends["t1"]) - 0.05
    assert abs(starts["t0"] - starts["t1"]) < 0.2


def test_memory_used_by_other_processes_counts(fake_gpu):
    fake_gpu["external"] = 20000  # e.g. another program on the card
    waited = []
    done = threading.Event()

    def worker():  # type: ignore[no-untyped-def]
        with gpu.admitted("big", 6000, on_wait=lambda n, f: waited.append(f)):
            done.set()

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.3)
    assert not done.is_set() and waited and waited[-1] < 6000
    fake_gpu["external"] = 0
    t.join(5)
    assert done.is_set()


def test_a_model_larger_than_the_card_fails_fast(fake_gpu):
    with pytest.raises(gpu.GpuTooSmall), gpu.admitted("huge", 30000, on_wait=lambda n, f: None):
        pass


def test_long_waiting_tasks_are_served_first(fake_gpu, monkeypatch):
    monkeypatch.setattr(gpu, "AGING_SECONDS", 0.2)
    log: list = []
    holder = threading.Thread(target=run_admitted, args=("holder", 20000, log, 0.8))
    holder.start()
    time.sleep(0.05)
    big = threading.Thread(target=run_admitted, args=("big", 20000, log, 0.1))
    big.start()
    time.sleep(0.4)  # 'big' has now waited past the aging limit
    small = threading.Thread(target=run_admitted, args=("small", 2000, log, 0.1))
    small.start()
    for t in (holder, big, small):
        t.join(10)
    starts = {task: at for kind, task, at in log if kind == "start"}
    assert starts["small"] >= starts["big"], "a small task must not jump ahead of an aged large one"


def test_reservations_of_dead_workers_expire(fake_gpu, redis_ok, monkeypatch):
    host = gpu.config().hostname
    key = f"sml:gpu-reservations:{host}:{gpu.gpu_index()}"
    redis_ok.hset(key, "dead-task", '{"mb": 20000, "expires": 1}')  # expired long ago
    with gpu.admitted("alive", 20000, on_wait=lambda n, f: None):
        assert redis_ok.hexists(key, "alive") and not redis_ok.hexists(key, "dead-task")


def test_observed_peaks_raise_the_requirement(redis_ok, monkeypatch):
    model = f"model:test-{uuid.uuid4().hex[:6]}"
    try:
        assert gpu.need_mb(model, 6000, 24000) == 6000  # nothing observed yet: the declaration
        assert gpu.need_mb(model, 40000, 24000) == int((24000 - gpu.MARGIN_MB) * gpu.CAP_FRACTION)  # capped
        gpu.record_peak(model, 3000)
        gpu.record_peak(model, 2000)  # lower peaks never shrink it
        assert gpu.need_mb(model, 40000, 24000) == int(3000 * gpu.HEADROOM)  # observation replaces a guess
    finally:
        redis_ok.hdel(gpu.PEAKS_KEY, model)


def test_an_oversized_declaration_still_runs_alone_on_an_idle_card(fake_gpu, monkeypatch):
    """Regression: a need capped at the card's size never fitted because idle cards report a few MB."""
    monkeypatch.setattr(gpu, "AGING_SECONDS", 0.1)
    fake_gpu["external"] = 300  # idle driver memory
    need = gpu.need_mb("model:none", 40000, fake_gpu["total"])
    with gpu.admitted("oversized", need, on_wait=lambda n, f: None):
        pass


def test_a_task_that_cannot_fit_does_not_block_others(fake_gpu, monkeypatch):
    monkeypatch.setattr(gpu, "AGING_SECONDS", 0.1)
    fake_gpu["external"] = 15000  # another program holds most of the card
    log: list = []
    blocked = threading.Thread(target=run_admitted, args=("needs-20g", 20000, log, 0.1), daemon=True)
    blocked.start()
    time.sleep(0.3)  # the big task is now 'aged' but cannot fit while the other program runs
    small = threading.Thread(target=run_admitted, args=("small", 2000, log, 0.1))
    small.start()
    small.join(5)
    assert ("end", "small") in [(k, t) for k, t, _ in log]
    fake_gpu["external"] = 0
    blocked.join(5)
