"""Retention, priority and concurrency limits derived from the user's plan."""

from __future__ import annotations

from typing import Any

from sml.core.models import PlatformSettings

TRIAL_RETENTION_DAYS = 1
# RabbitMQ message priority (0-9, higher first). Web traffic outranks API bulk.
PLAN_PRIORITY = {0: 4, 1: 6, 2: 8}
FREE_PRIORITY = 3
TRIAL_PRIORITY = 2


def active_plan(user: Any) -> Any:
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    sub = (user.subscriptions.filter(status__in=["active", "past_due"]).select_related("plan")
           .order_by("-created_at").first())
    return sub.plan if sub else None


def retention_days_for(user: Any) -> int:
    if user is None:
        return TRIAL_RETENTION_DAYS
    policy = getattr(user, "access_policy", None)
    if policy is not None and policy.retention_days_override:
        return policy.retention_days_override
    plan = active_plan(user)
    return plan.retention_days if plan else PlatformSettings.load().free_retention_days


def priority_for(user: Any, source: str) -> int:
    if user is None or source == "trial":
        return TRIAL_PRIORITY
    plan = active_plan(user)
    base = PLAN_PRIORITY.get(plan.priority, 4) if plan else FREE_PRIORITY
    return min(9, base + (1 if source == "web" else 0))


def max_inflight_for(user: Any) -> int:
    cfg = PlatformSettings.load()
    if user is None:
        return 2
    policy = getattr(user, "access_policy", None)
    if policy is not None and policy.max_inflight_tasks:
        return policy.max_inflight_tasks
    plan = active_plan(user)
    return plan.max_inflight_tasks if plan else cfg.free_max_inflight_tasks
