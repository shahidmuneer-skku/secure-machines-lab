"""The image studio's models (config/studio.yaml, read by the studio server too) and their live state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import redis
import yaml
from django.conf import settings

from sml.jobs.live import redis_or_none

logger = logging.getLogger(__name__)

MODES = ("generate", "edit")
KEEP_KEY = "sml:studio:keep"  # the admin's models, read by the resident supervisor
SERVER_KEY = "sml:resident:studio"  # the studio server's status, published by the supervisor


@dataclass(frozen=True)
class StudioModel:
    id: str
    name: str
    vendor: str
    license: str
    commercial: bool
    repo: str
    modes: tuple[str, ...]
    call: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)

    def supports(self, mode: str) -> bool:
        return mode in self.modes

    def controls(self, mode: str, limits: dict[str, Any]) -> dict[str, Any]:
        """What the studio offers for this model in `mode`; the API accepts nothing else."""
        caps, call = self.capabilities, self.call
        size = call.get("size")
        sized = size is True or size == mode
        ratios = [{"id": ratio, "width": int(wh[0]), "height": int(wh[1])}
                  for ratio, wh in (caps.get("aspect_ratios") or {}).items()] if sized else []
        steps = caps.get("steps") if call.get("steps") else None
        guidance = caps.get("guidance") if call.get("guidance") else None
        return {
            "references": {"min": 1, "max": int(caps.get("max_references", 0))} if mode == "edit"
            else {"min": 0, "max": 0},
            "aspect_ratios": ratios,
            # Edits follow the reference image unless a format is chosen.
            "match_input": mode == "edit",
            "negative_prompt": bool(caps.get("negative_prompt")) and bool(call.get("negative_prompt")),
            "transparent": bool(caps.get("transparent")),
            "steps": dict(steps) if steps else None,
            "guidance": dict(guidance) if guidance else None,
            "max_outputs": int(caps.get("max_outputs", 1)),
            "prompt_max_chars": int(limits.get("prompt_max_chars", 2000)),
        }


@dataclass(frozen=True)
class StudioRegistry:
    models: dict[str, StudioModel]
    limits: dict[str, Any]

    def get(self, model_id: str) -> StudioModel | None:
        return self.models.get(model_id)

    def for_mode(self, mode: str) -> list[StudioModel]:
        return [m for m in self.models.values() if m.supports(mode)]


@lru_cache(maxsize=1)
def registry() -> StudioRegistry:
    path = settings.STUDIO_CONFIG_PATH
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    models = {}
    for m in raw.get("models") or []:
        models[m["id"]] = StudioModel(
            id=m["id"], name=m.get("name", m["id"]), vendor=m.get("vendor", ""), license=m.get("license", ""),
            commercial=bool(m.get("commercial", False)), repo=m.get("repo", ""),
            modes=tuple(x for x in m.get("modes", []) if x in MODES), call=dict(m.get("call") or {}),
            capabilities=dict(m.get("capabilities") or {}))
    return StudioRegistry(models=models, limits=dict(raw.get("limits") or {}))


def server_status() -> dict[str, Any]:
    """The studio server as the supervisor last saw it: state plus loaded/installed models."""
    r = redis_or_none()
    if r is None:
        return {"state": "unknown"}
    try:
        raw = r.get(SERVER_KEY)
    except redis.RedisError:
        return {"state": "unknown"}
    if not raw:
        return {"state": "down"}
    try:
        status = json.loads(raw)
    except ValueError:
        return {"state": "unknown"}
    studio = status.get("studio") or {}
    return {"state": status.get("state", "down"), "gpu": str(status.get("gpu", "")),
            "loaded": list(studio.get("loaded") or []), "loading": studio.get("loading"),
            "busy": bool(studio.get("busy")), "waiting": int(studio.get("waiting") or 0),
            "device_free_gb": studio.get("device_free_gb"), "budget_gb": studio.get("budget_gb"),
            "models": studio.get("models") or {}}


def publish_keep(model_ids: list[str]) -> None:
    """Tell the studio server which models to keep loaded (the supervisor hands it over)."""
    r = redis_or_none()
    if r is None:
        return
    try:
        r.set(KEEP_KEY, json.dumps(list(dict.fromkeys(m for m in model_ids if m))))
    except redis.RedisError:
        logger.warning("Could not publish the studio's models", exc_info=True)
