"""Loads the model registry (config/models.yaml) and applies admin overrides.

The same YAML is read by the worker runtime, so the API and the workers agree on
model ids, queues and invocation templates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

OVERRIDES_CACHE_KEY = "model-overrides:v5"


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
    runs_on: frozenset[str]  # media types this detector runs on in every job (admin-chosen)
    show_heatmap: bool  # users see this detector's heatmap (admin-chosen)
    trial: bool
    weight: float
    gpu_mem_mb: int
    media: dict[str, dict[str, Any]]
    legacy_ids: list[str] = field(default_factory=list)
    variant_of: str | None = None
    fallbacks: dict[str, Any] = field(default_factory=dict)
    # A detector that is especially reliable at recognising authentic files counts more when it says
    # authentic (score below the threshold), and that answer can also count in the other analysis.
    authentic_boost: float = 1.0
    authentic_counts_in_all: bool = False

    def name(self, lang: str = "en") -> str:
        return self.display_name.get(lang) or self.display_name.get("en") or self.id

    def supports(self, media_type: str) -> bool:
        return media_type in self.media

    def vote_weight(self, fake_prob: float, threshold: float) -> float:
        """This detector's weight for one score: boosted when it says authentic."""
        return self.weight * (self.authentic_boost if fake_prob < threshold else 1.0)

    def counts_in(self, family: str, fake_prob: float, threshold: float) -> bool:
        """Whether this score counts in the analysis of `family`: always in its own analysis, and in
        the other one when it says authentic and `authentic_counts_in_all` is set."""
        return self.family == family or (self.authentic_counts_in_all and fake_prob < threshold)

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


def _family(model_id: str, family: str | None) -> str:
    if family in FAMILIES:
        return family
    logger.warning("Model %s has family %r; counting it towards the AI-generation analysis", model_id, family)
    return "ai_generated"


def _runs_on(raw_model: dict[str, Any], override: dict[str, Any]) -> frozenset[str]:
    """Media types the detector runs on: the admin's per-media choice, else models.yaml's
    `default_selected` (which applies to every media type the detector supports)."""
    default = bool(raw_model.get("default_selected", False))
    chosen = set()
    for media in raw_model.get("media", {}):
        flag = override.get(f"run_on_{media}")
        if flag if flag is not None else default:
            chosen.add(media)
    return frozenset(chosen)


# Result groups users see, in display order (the detectors' families; ADR 0011): the face-swap
# analysis and the AI-generation analysis (owner, 2026-10-01: no separate "general" analysis).
FAMILIES = ("deepfake", "ai_generated")


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
                family=_family(m["id"], ov.get("family") or m.get("family")),
                face_required=bool(m.get("face_required", False)),
                xai=m.get("xai", "none"),
                enabled=ov.get("enabled") if ov.get("enabled") is not None else bool(m.get("enabled", True)),
                runs_on=_runs_on(m, ov),
                show_heatmap=(ov["show_heatmap"] if ov.get("show_heatmap") is not None
                              else bool(m.get("show_heatmap", False))),
                trial=ov["trial"] if ov.get("trial") is not None else bool(m.get("trial", False)),
                weight=float(ov["weight"] if ov.get("weight") is not None
                             else m.get("weight", defaults.get("weight", 1.0))),
                gpu_mem_mb=int(m.get("gpu_mem_mb", defaults.get("gpu_mem_mb", 6000))),
                media=m.get("media", {}),
                legacy_ids=list(m.get("legacy_ids", [])),
                variant_of=m.get("variant_of"),
                fallbacks=m.get("fallbacks", {}) or {},
                authentic_boost=float(ov["authentic_boost"] if ov.get("authentic_boost") is not None
                                      else m.get("authentic_boost", 1.0)),
                authentic_counts_in_all=(ov["authentic_counts_in_all"]
                                         if ov.get("authentic_counts_in_all") is not None
                                         else bool(m.get("authentic_counts_in_all", False))),
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
        """The detectors every job of this media type runs (before per-user restrictions)."""
        return [m.id for m in self.enabled_for(media_type) if media_type in m.runs_on]

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
            o.model_id: {"enabled": o.enabled, "weight": o.weight, "run_on_image": o.run_on_image,
                         "run_on_video": o.run_on_video, "trial": o.trial, "show_heatmap": o.show_heatmap,
                         "family": o.family, "authentic_boost": o.authentic_boost,
                         "authentic_counts_in_all": o.authentic_counts_in_all}
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
