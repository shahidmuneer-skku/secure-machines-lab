from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .models import ApiKey


def require_scope(scope: str) -> type[BasePermission]:
    """API-key callers need `scope`; session callers are governed by role capabilities."""

    class _Scope(BasePermission):
        message = f"This API key lacks the '{scope}' scope."

        def has_permission(self, request: Request, view) -> bool:  # type: ignore[no-untyped-def]
            key = getattr(request, "auth", None)
            return not isinstance(key, ApiKey) or key.has_scope(scope)

    _Scope.__name__ = f"Scope_{scope.replace(':', '_')}"
    return _Scope
