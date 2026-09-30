"""One loaded LLM for all agent runs (news verification, explain-why), shared as long as it fits.

* At most SML_AGENT_PARALLEL agent runs use Ollama at once; the rest wait here (queue position
  is reported) instead of piling onto the GPU.
* Only one Ollama model is in use at a time: other loaded models that no run is using are
  unloaded, and a run for a different model waits until the current one is idle.
* The model is loaded once and pinned (keep_alive -1) with the same context size the runs use,
  so Ollama never reloads it between jobs.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator

import httpx
import redis

from ..clients import redis_client
from ..config import config
from ..gpu import reserve

logger = logging.getLogger(__name__)

PARALLEL = max(1, int(os.environ.get("SML_AGENT_PARALLEL", "2")))
SLOTS_KEY, WAITERS_KEY, MODELS_KEY = "sml:agent-slots", "sml:agent-waiters", "sml:agent-models"


def _base() -> str:
    return config().ollama_base_url.rstrip("/")


def loaded_models() -> list[str]:
    resp = httpx.get(f"{_base()}/api/ps", timeout=10)
    resp.raise_for_status()
    return [m.get("name") or m.get("model") for m in resp.json().get("models", [])]


def models_in_use(r: redis.Redis) -> set[str]:
    now = time.time()
    in_use = set()
    for _, raw in r.hgetall(MODELS_KEY).items():
        with contextlib.suppress(ValueError, TypeError):
            entry = json.loads(raw)
            if entry["expires"] > now:
                in_use.add(entry["model"])
    return in_use


def prepare(model: str, num_ctx: int, on_step: Callable[[str], None]) -> None:
    """Unload idle other models, then load and pin ours once (same options as the runs)."""
    try:
        loaded = loaded_models()
    except httpx.HTTPError:
        logger.warning("Ollama not reachable for model management", exc_info=True)
        return
    busy = models_in_use(redis_client())
    for other in loaded:
        if other != model and other not in busy:
            on_step(f"Unloading idle model {other}")
            with contextlib.suppress(httpx.HTTPError):
                httpx.post(f"{_base()}/api/generate", json={"model": other, "keep_alive": 0}, timeout=60)
    if model not in loaded:
        on_step(f"Loading {model} (once; it stays loaded for later runs)")
    # Also refreshes the pin if the model is already loaded; same num_ctx means no reload.
    with contextlib.suppress(httpx.HTTPError):
        httpx.post(f"{_base()}/api/generate", timeout=900,
                   json={"model": model, "keep_alive": -1, "options": {"num_ctx": num_ctx}})


@contextlib.contextmanager
def slot(model: str, num_ctx: int, on_step: Callable[[str], None],
         check_cancel: Callable[[], None] = lambda: None) -> Iterator[None]:
    """Wait for an agent slot on `model`, make sure it is the one loaded model, run, release."""
    owner = f"agent-{uuid.uuid4().hex}"
    try:
        r = redis_client()
        r.ping()
    except redis.RedisError:
        logger.warning("Redis unavailable; agent run without slot control", exc_info=True)
        yield
        return

    def capacity(_reserved: int) -> int:
        others = models_in_use(r) - {model}
        return 0 if others else PARALLEL  # another model is serving runs: wait until it is idle

    last_note = [0.0]

    def waiting(_need: int, free: int) -> None:
        if time.monotonic() - last_note[0] > 15:
            on_step("Waiting for the AI model (other analyses are using it)")
            last_note[0] = time.monotonic()

    with reserve(SLOTS_KEY, WAITERS_KEY, owner, 1, capacity, waiting, check_cancel):
        stop = [False]

        def mark() -> None:
            r.hset(MODELS_KEY, owner, json.dumps({"model": model, "expires": time.time() + 90}))

        mark()
        try:
            prepare(model, num_ctx, on_step)

            def renew() -> None:
                while not stop[0]:
                    time.sleep(30)
                    with contextlib.suppress(redis.RedisError):
                        mark()

            threading.Thread(target=renew, daemon=True).start()
            yield
        finally:
            stop[0] = True
            with contextlib.suppress(redis.RedisError):
                r.hdel(MODELS_KEY, owner)
