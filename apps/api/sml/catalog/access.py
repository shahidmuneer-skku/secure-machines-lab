"""What a job runs and who may run it.

Users never choose detectors or checks: every detection job runs the admin's set for its media
type (Admin → Models) and the admin's extra checks (Admin → Settings), narrowed by the user's
AccessPolicy. Modules (detect / long-form video / news) are gated by role capability ∩ policy.
"""

from __future__ import annotations

from typing import Any

from sml.core.exceptions import ModelNotAllowed, ModuleNotAllowed
from sml.core.permissions import has_capability

from .registry import ModelSpec, registry

MODULE_CAPABILITY = {
    "detect": "run_detection",
    "long_video": "run_long_video",
    "news": "run_news_verification",
    "studio": "use_studio",
    "assistant": "use_assistant",
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


def model_allowed(user: Any, model: ModelSpec) -> bool:
    if not model.enabled:
        return False
    policy = _policy(user)
    return policy is None or policy.allows_model(model.id)


def detectors_for(user: Any, media_type: str) -> list[str]:
    """The detectors a job of this media type runs for this user (admin's set ∩ user policy)."""
    reg = registry()
    chosen = [m for m in reg.default_selection(media_type) if model_allowed(user, reg.models[m])]
    if not chosen:
        # The message never lists detectors; the operator sees why in the admin console.
        raise ModelNotAllowed(f"Analysis of {media_type}s is not available for your account right now.")
    return chosen


def allowed_audit_steps(user: Any) -> list[str]:
    policy = _policy(user)
    return [s for s in registry().audit_steps if policy is None or policy.allows_audit_step(s)]


def checks_for(user: Any) -> list[str]:
    """The admin's extra checks (face, safety, fas) this user's policy permits, plus metadata."""
    from sml.core.models import PlatformSettings

    reg = registry()
    allowed = set(allowed_audit_steps(user))
    extra = [s for s in PlatformSettings.load().audit_steps or [] if s in reg.audit_steps and s in allowed
             and not reg.audit_steps[s].builtin]
    builtin = [s.id for s in reg.audit_steps.values() if s.builtin]
    return builtin + extra
