"""The assistant's language model: Ollama's chat API, streamed (owner, 2026-10-02: qwen3.6:27b).

The model is the one the reasoning worker keeps loaded; requests use the same context size and
keep-alive (sml_worker.agents.engine), so a chat never makes Ollama reload it. Ollama serves one
request at a time per loaded model: a chat reply waits while an explanation or a news report is
being written.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

IMAGE_MAX_SIDE = 1024
MAX_IMAGES = 4


class AssistantUnavailable(Exception):
    """The language model could not be reached or failed."""


def payload(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": settings.ASSISTANT_MODEL,
        "messages": messages,
        "stream": True,
        "think": False,
        "keep_alive": -1,
        "options": {"num_ctx": settings.ASSISTANT_NUM_CTX, "temperature": 0.4},
    }


async def chat_stream(messages: list[dict[str, Any]]) -> AsyncIterator[str]:
    """Yields the reply's text as it is generated."""
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    timeout = httpx.Timeout(connect=5.0, read=settings.ASSISTANT_READ_TIMEOUT, write=30.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client, \
                client.stream("POST", url, json=payload(messages)) as resp:
            if resp.status_code != 200:
                body = (await resp.aread())[:300]
                raise AssistantUnavailable(f"Ollama answered {resp.status_code}: {body!r}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise AssistantUnavailable(str(data["error"])[:300])
                text = (data.get("message") or {}).get("content") or ""
                if text:
                    yield text
                if data.get("done"):
                    return
    except httpx.HTTPError as exc:
        raise AssistantUnavailable(str(exc)) from exc


def image_b64(raw: bytes) -> str | None:
    """A JPEG of at most IMAGE_MAX_SIDE pixels, base64-encoded, for the model to look at."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return base64.b64encode(out.getvalue()).decode()
    except Exception:  # an unreadable image is simply not shown to the model
        logger.warning("Could not prepare an image for the assistant", exc_info=True)
        return None
