"""Seeds roles (groups) and their capabilities from config/roles.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import transaction

from .models import CAPABILITY_CODENAMES, RoleProfile


def _flatten(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, list):
            out.extend(_flatten(item))
        else:
            out.append(str(item))
    return out


def load_roles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(Path(path or settings.ROLES_CONFIG_PATH).read_text())
    return data["roles"]


@transaction.atomic
def seed_roles(path: Path | None = None) -> list[str]:
    roles = load_roles(path)
    perms = {p.codename: p for p in Permission.objects.filter(
        content_type__app_label="accounts", codename__in=CAPABILITY_CODENAMES)}
    missing = set(CAPABILITY_CODENAMES) - set(perms)
    if missing:
        raise RuntimeError(f"Capabilities missing from the database (run migrate first): {sorted(missing)}")

    for name, spec in roles.items():
        caps = _flatten(spec.get("capabilities", []))
        codenames = CAPABILITY_CODENAMES if "*" in caps else caps
        unknown = set(codenames) - set(CAPABILITY_CODENAMES)
        if unknown:
            raise ValueError(f"Role {name!r} references unknown capabilities: {sorted(unknown)}")
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.set([perms[c] for c in codenames])
        RoleProfile.objects.update_or_create(
            group=group,
            defaults={
                "description": spec.get("description", ""),
                "mfa_required": bool(spec.get("mfa_required", False)),
                "is_staff_role": bool(spec.get("staff", False)),
                "is_default": bool(spec.get("default", False)),
                "is_system": True,
            },
        )
    return list(roles)


def sync_staff_flag(user) -> None:  # type: ignore[no-untyped-def]
    """Keep `is_staff` aligned with whether the user holds any staff role."""
    is_staff = user.groups.filter(role_profile__is_staff_role=True).exists()
    if user.is_staff != is_staff:
        user.is_staff = is_staff
        user.save(update_fields=["is_staff"])
