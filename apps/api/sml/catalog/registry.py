"""Loads the model registry (config/models.yaml) and applies admin overrides.

The same YAML is read by the worker runtime, so the API and the workers agree on
model ids, queues and invocation templates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.cache import cache

OVERRIDES_CACHE_KEY = "model-overrides:v1"


def model_queue(model_id: str) -> str:
    return f"sml.model.{model_id}"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    display_name: dict[str, str]
    description: dict[str, str]
    family: str
    face_required: bool
    xai: str
    enabled: bool
    default_selected: bool
    trial: bool
    weight: float
    gpu_mem_mb: int
    media: dict[str, dict[str, Any]]
    legacy_ids: list[str] = field(default_factory=list)
    variant_of: str | None = None
    fallbacks: dict[str, Any] = field(default_factory=dict)

    def name(self, lang: str = "en") -> str:
        return self.display_name.get(lang) or self.display_name.get("en") or self.id

    def supports(self, media_type: str) -> bool:
        return media_type in self.media

    @property
    def queue(self) -> str:
        return model_queue(self.id)

    def timeout(self, media_type: str, default: int) -> int:
        return int(self.media.get(media_type, {}).get("timeout_seconds", default))


@dataclass(frozen=True)
class LongVideoModelSpec:
    id: str
    display_name: dict[str, str]
    description: dict[str, str]
    default_selected: bool
    config: dict[str, Any]

    def name(self, lang: str = "en") -> str:
        return self.display_name.get(lang) or self.display_name.get("en") or self.id


@dataclass(frozen=True)
class AuditStepSpec:
    id: str
    display_name: dict[str, str]
    description: dict[str, str]
    builtin: bool
    config: dict[str, Any]

    def name(self, lang: str = "en") -> str:
        return self.display_name.get(lang) or self.display_name.get("en") or self.id


class Registry:
    def __init__(self, raw: dict[str, Any], overrides: dict[str, dict[str, Any]]):
        defaults = raw.get("defaults", {})
        self.defaults = defaults
        self.models: dict[str, ModelSpec] = {}
        self.aliases: dict[str, str] = {}
        for m in raw.get("models", []):
            ov = overrides.get(m["id"], {})
            spec = ModelSpec(
                id=m["id"],
                display_name=m.get("display_name", {"en": m["id"]}),
                description=m.get("description", {}),
                family=m.get("family", "general"),
                face_required=bool(m.get("face_required", False)),
                xai=m.get("xai", "none"),
                enabled=ov.get("enabled") if ov.get("enabled") is not None else bool(m.get("enabled", True)),
                default_selected=(ov["default_selected"] if ov.get("default_selected") is not None
                                  else bool(m.get("default_selected", False))),
                trial=ov["trial"] if ov.get("trial") is not None else bool(m.get("trial", False)),
                weight=float(ov["weight"] if ov.get("weight") is not None
                             else m.get("weight", defaults.get("weight", 1.0))),
                gpu_mem_mb=int(m.get("gpu_mem_mb", defaults.get("gpu_mem_mb", 6000))),
                media=m.get("media", {}),
                legacy_ids=list(m.get("legacy_ids", [])),
                variant_of=m.get("variant_of"),
                fallbacks=m.get("fallbacks", {}) or {},
            )
            self.models[spec.id] = spec
            for alias in spec.legacy_ids:
                self.aliases.setdefault(alias.lower(), spec.id)
        self.long_video_models = {
            m["id"]: LongVideoModelSpec(m["id"], m.get("display_name", {}), m.get("description", {}),
                                        bool(m.get("default_selected", False)), m)
            for m in raw.get("long_video_models", [])
        }
        self.audit_steps = {
            s["id"]: AuditStepSpec(s["id"], s.get("display_name", {}), s.get("description", {}),
                                   bool(s.get("builtin", False)), s)
            for s in raw.get("audit_steps", [])
        }

    def get(self, model_id: str) -> ModelSpec | None:
        return self.models.get(model_id) or self.models.get(self.aliases.get(model_id.lower(), ""))

    def enabled_for(self, media_type: str) -> list[ModelSpec]:
        return [m for m in self.models.values() if m.enabled and m.supports(media_type)]

    def default_selection(self, media_type: str) -> list[str]:
        return [m.id for m in self.enabled_for(media_type) if m.default_selected]

    def trial_selection(self) -> list[str]:
        return [m.id for m in self.enabled_for("image") if m.trial]


@lru_cache(maxsize=4)
def _load_yaml(path: str, mtime: float) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text())


def _overrides() -> dict[str, dict[str, Any]]:
    data = cache.get(OVERRIDES_CACHE_KEY)
    if data is None:
        from .models import ModelOverride

        data = {
            o.model_id: {"enabled": o.enabled, "weight": o.weight, "default_selected": o.default_selected,
                         "trial": o.trial}
            for o in ModelOverride.objects.all()
        }
        cache.set(OVERRIDES_CACHE_KEY, data, 30)
    return data


def registry() -> Registry:
    path = Path(settings.MODELS_CONFIG_PATH)
    raw = _load_yaml(str(path), path.stat().st_mtime)
    return Registry(raw, _overrides())


def invalidate_overrides() -> None:
    cache.delete(OVERRIDES_CACHE_KEY)
