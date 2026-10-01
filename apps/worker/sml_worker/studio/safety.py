"""Prompt check for the image studio (owner, 2026-10-01: refuse sexual and violent requests).

The platform's local LLM (Ollama, the reasoning model already loaded for the agents) classifies the
prompt; requests it refuses are not charged. The check fails closed: when the LLM cannot be reached
the request is not run. Reference images and outputs are checked by the studio server's NSFW
classifier.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from ..agents.engine import NUM_CTX
from ..config import config

logger = logging.getLogger(__name__)

# Never sent to the LLM: refused outright.
_MINORS = (r"(child|children|kid|kids|minor|minors|underage|under-age|teen|teens|preteen|toddler|infant|baby|loli"
           r"|shota|아동|미성년|어린이|초등학생|중학생|kinder|minderjährig)")
_SEXUAL = (r"(nude|naked|nsfw|sex|sexual|porn|erotic|lingerie|undress|topless|explicit|야한|노출|누드|성적|nackt"
           r"|erotisch|sexuell)")
# Latin words must stand alone (no "sextant"); Korean words take particles, so they match inside words.
_M, _S = rf"(?<![a-z]){_MINORS}(?![a-z])", rf"(?<![a-z]){_SEXUAL}(?![a-z])"
_BLOCK = [re.compile(rf"{_M}.*{_S}|{_S}.*{_M}", re.IGNORECASE | re.DOTALL)]

POLICY = """You are the content-safety filter of an image generation and editing service.
Decide whether the user's request may be generated. Refuse (allowed=false) requests for:
- sexual content: nudity, sexual acts, erotic or fetish imagery, undressing a person, sexualised poses;
- any sexual or suggestive content involving minors (always refuse);
- graphic violence: gore, mutilation, torture, killing, serious injury, self-harm, suicide;
- hateful or extremist imagery (e.g. Nazi propaganda, terrorist symbols used approvingly).
Allow everything else, including ordinary people, portraits, fashion, swimwear in a non-sexual context,
historical or cartoon action without gore, and edits of photos. The request may be in any language.
Answer only with JSON: {"allowed": true|false, "category": "sexual|minors|violence|hate|none", "reason": "<short>"}"""


class SafetyUnavailable(Exception):
    pass


@dataclass
class Verdict:
    allowed: bool
    category: str = "none"
    reason: str = ""


def check_prompt(prompt: str, negative_prompt: str, model: str, *, timeout: float = 300) -> Verdict:
    text = prompt.strip()
    for pattern in _BLOCK:
        if pattern.search(text):
            return Verdict(False, "minors", "Sexual content involving minors.")
    request = f"Request: {text}"
    if negative_prompt.strip():
        request += f"\nThings to avoid in the image: {negative_prompt.strip()}"
    payload = {
        "model": model, "stream": False, "think": False, "format": "json", "keep_alive": -1,
        # Same context size as the agents, so Ollama does not reload the model for this call.
        "options": {"num_ctx": NUM_CTX.get(model, 32768), "temperature": 0},
        "messages": [{"role": "system", "content": POLICY}, {"role": "user", "content": request}],
    }
    last_error: Exception | None = None
    for _ in range(2):
        try:
            resp = httpx.post(config().ollama_base_url.rstrip("/") + "/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            answer = json.loads((resp.json().get("message") or {}).get("content") or "{}")
            allowed = answer.get("allowed")
            if not isinstance(allowed, bool):
                raise ValueError(f"unexpected answer {answer!r}")
            return Verdict(allowed, str(answer.get("category") or "none")[:32], str(answer.get("reason") or "")[:300])
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            logger.warning("Prompt check failed: %s", exc)
    raise SafetyUnavailable(f"The prompt check is unavailable: {last_error}")
