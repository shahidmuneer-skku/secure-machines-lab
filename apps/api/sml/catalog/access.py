"""Effective access = role capabilities ∩ user AccessPolicy ∩ API-key restrictions."""

from __future__ import annotations

from typing import Any

from sml.core.exceptions import ModelNotAllowed, ModuleNotAllowed
from sml.core.permissions import has_capability

from .registry import ModelSpec, registry

MODULE_CAPABILITY = {
    "detect": "run_detection",
    "long_video": "run_long_video",
    "news": "run_news_verification",
}


def _policy(user: Any) -> Any:
    return getattr(user, "access_policy", None)


def module_allowed(user: Any, module: str) -> bool:
    if not has_capability(user, MODULE_CAPABILITY[module]):
        return False
    policy = _policy(user)
    return policy is None or policy.allows_module(module)


def assert_module_allowed(user: Any, module: str) -> None:
    if not module_allowed(user, module):
        raise ModuleNotAllowed()


def model_allowed(user: Any, model: ModelSpec, api_key: Any = None) -> bool:
    if not model.enabled:
        return False
    policy = _policy(user)
    if policy is not None and not policy.allows_model(model.id):
        return False
    return api_key is None or not hasattr(api_key, "model_allowed") or api_key.model_allowed(model.id)


def allowed_models(user: Any, media_type: str, api_key: Any = None) -> list[ModelSpec]:
    return [m for m in registry().enabled_for(media_type) if model_allowed(user, m, api_key)]


def resolve_models(user: Any, media_type: str, requested: list[str] | None, api_key: Any = None) -> list[str]:
    """Validates a model selection. Empty/None → the default selection the caller may use."""
    reg = registry()
    allowed = {m.id for m in allowed_models(user, media_type, api_key)}
    if not requested:
        chosen = [m for m in reg.default_selection(media_type) if m in allowed] or sorted(allowed)[:3]
        if not chosen:
            raise ModelNotAllowed("No detection models are available to your account for this media type.")
        return chosen
    resolved: list[str] = []
    rejected: list[str] = []
    for raw in requested:
        spec = reg.get(raw)
        if spec is None or not spec.supports(media_type) or spec.id not in allowed:
            rejected.append(raw)
        elif spec.id not in resolved:
            resolved.append(spec.id)
    if rejected:
        raise ModelNotAllowed(
            f"Not available for {media_type}: {', '.join(rejected)}", extra={"models": rejected}
        )
    return resolved


def allowed_audit_steps(user: Any) -> list[str]:
    policy = _policy(user)
    return [s for s in registry().audit_steps if policy is None or policy.allows_audit_step(s)]
