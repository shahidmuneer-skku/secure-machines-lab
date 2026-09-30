"""Agent runs share one loaded model: bounded parallelism, one model at a time (Redis required)."""

from __future__ import annotations

import threading
import time

import pytest

from sml_worker import gpu
from sml_worker.agents import ollama


@pytest.fixture(autouse=True)
def isolated(monkeypatch):  # type: ignore[no-untyped-def]
    from sml_worker.clients import redis_client

    try:
        redis_client().ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Redis not reachable")
    suffix = str(time.time_ns())
    monkeypatch.setattr(ollama, "SLOTS_KEY", f"sml:test-agent-slots:{suffix}")
    monkeypatch.setattr(ollama, "WAITERS_KEY", f"sml:test-agent-waiters:{suffix}")
    monkeypatch.setattr(ollama, "MODELS_KEY", f"sml:test-agent-models:{suffix}")
    monkeypatch.setattr(ollama, "PARALLEL", 2)
    monkeypatch.setattr(gpu, "POLL_SECONDS", 0.05)
    prepared: list[str] = []
    monkeypatch.setattr(ollama, "prepare", lambda model, num_ctx, on_step: prepared.append(model))
    yield prepared
    r = redis_client()
    for key in (ollama.SLOTS_KEY, ollama.WAITERS_KEY, ollama.MODELS_KEY):
        r.delete(key)


def run(model: str, log: list, hold: float = 0.3) -> None:
    with ollama.slot(model, 32768, on_step=lambda s: None):
        log.append(("start", model, time.monotonic()))
        time.sleep(hold)
        log.append(("end", model, time.monotonic()))


def peak_concurrency(log: list) -> int:
    running = peak = 0
    for kind, _, _ in sorted(log, key=lambda e: e[2]):
        running += 1 if kind == "start" else -1
        peak = max(peak, running)
    return peak


def test_at_most_parallel_runs_share_the_model(isolated):
    log: list = []
    threads = [threading.Thread(target=run, args=("qwen", log)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len([e for e in log if e[0] == "start"]) == 4
    assert peak_concurrency(log) == 2


def test_a_different_model_waits_until_the_current_one_is_idle(isolated):
    log: list = []
    first = threading.Thread(target=run, args=("model-a", log, 0.4))
    first.start()
    time.sleep(0.1)
    second = threading.Thread(target=run, args=("model-b", log, 0.1))
    second.start()
    first.join(10)
    second.join(10)
    starts = {m: at for kind, m, at in log if kind == "start"}
    ends = {m: at for kind, m, at in log if kind == "end"}
    assert starts["model-b"] >= ends["model-a"] - 0.01
    assert isolated == ["model-a", "model-b"]  # each model prepared (loaded/pinned) once per run
