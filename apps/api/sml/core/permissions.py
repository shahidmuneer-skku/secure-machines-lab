"""Permission-based RBAC for DRF views.

Roles are Django groups seeded from config/roles.yaml; each bundles
permissions declared on `accounts.Capability`. Views declare the permission
codenames they need; the frontend only hides UI, the API is authoritative.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .exceptions import MfaRequired

PERM_PREFIX = "accounts."


def has_capability(user, codename: str) -> bool:  # type: ignore[no-untyped-def]
    return bool(user and user.is_authenticated and user.is_active and user.has_perm(PERM_PREFIX + codename))


def require(*codenames: str) -> type[BasePermission]:
    """`permission_classes = [require("view_users")]` → caller needs all listed capabilities."""

    class _Required(BasePermission):
        message = "You do not have permission to perform this action."

        def has_permission(self, request: Request, view) -> bool:  # type: ignore[no-untyped-def]
            return all(has_capability(request.user, c) for c in codenames)

    _Required.__name__ = "Require_" + "_".join(codenames)
    return _Required


class SessionOnly(BasePermission):
    """Rejects API-key principals (admin and account-security endpoints are browser-only)."""

    message = "This endpoint is not available to API keys."

    def has_permission(self, request: Request, view) -> bool:  # type: ignore[no-untyped-def]
        return getattr(request, "auth", None) is None or not hasattr(request.auth, "prefix")


class StaffMfaVerified(BasePermission):
    """Staff roles must use a session that completed two-factor authentication."""

    def has_permission(self, request: Request, view) -> bool:  # type: ignore[no-untyped-def]
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not user.requires_mfa:
            return True
        from allauth.account.authentication import get_authentication_records

        records = get_authentication_records(request) if hasattr(request, "session") else []
        if any(r.get("method") == "mfa" for r in records):
            return True
        raise MfaRequired()


def admin_permissions(*codenames: str) -> list[type[BasePermission]]:
    """Standard stack for /admin endpoints."""
    return [SessionOnly, StaffMfaVerified, require(*codenames)]
