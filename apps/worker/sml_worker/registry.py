"""Reads config/models.yaml (the same file the API uses)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from .config import config


@lru_cache(maxsize=1)
def raw_registry() -> dict[str, Any]:
    return yaml.safe_load(config().models_config.read_text())


def model_spec(model_id: str) -> dict[str, Any] | None:
    return next((m for m in raw_registry().get("models", []) if m["id"] == model_id), None)


def long_video_spec(model_id: str) -> dict[str, Any] | None:
    return next((m for m in raw_registry().get("long_video_models", []) if m["id"] == model_id), None)


def audit_spec(step_id: str) -> dict[str, Any] | None:
    return next((s for s in raw_registry().get("audit_steps", []) if s["id"] == step_id), None)


AGENT_QUEUES = ["sml.news", "sml.reasoning"]


def detector_queues() -> list[str]:
    """Queues whose tasks run a model on this worker's GPU (admitted by GPU memory)."""
    raw = raw_registry()
    names = [f"sml.model.{m['id']}" for m in raw.get("models", [])]
    names += [f"sml.audit.{s['id']}" for s in raw.get("audit_steps", [])]
    names += [f"sml.longvideo.{m['id']}" for m in raw.get("long_video_models", [])]
    return names


def queue_names() -> list[str]:
    return [*detector_queues(), *AGENT_QUEUES]
