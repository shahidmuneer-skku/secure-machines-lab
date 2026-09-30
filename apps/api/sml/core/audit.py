"""Helper for writing audit-log entries from views and services."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .middleware import client_ip, current_request_id
from .models import AuditLog


def record(
    action: str,
    *,
    request: HttpRequest | None = None,
    actor: Any = None,
    target: Any = None,
    target_type: str = "",
    target_id: str = "",
    target_label: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    if actor is None and request is not None and getattr(request, "user", None) is not None:
        actor = request.user if request.user.is_authenticated else None
    if target is not None:
        target_type = target_type or target._meta.label_lower
        target_id = target_id or str(target.pk)
        target_label = target_label or str(target)[:255]
    return AuditLog.objects.create(
        actor=actor,
        actor_label=(getattr(actor, "email", "") or "system")[:255],
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        before=before,
        after=after,
        ip=client_ip(request) if request is not None else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:512] if request is not None else ""),
        request_id=current_request_id(),
    )
