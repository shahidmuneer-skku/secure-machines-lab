"""drf-spectacular hooks."""

from __future__ import annotations

from typing import Any

# Response properties that really can be absent from a payload.
OPTIONAL_RESPONSE_FIELDS = {
    "Count": {"removed", "revoked"},
}

ADMIN_PREFIX = "/api/v1/admin/"


def exclude_admin_endpoints(endpoints: list[Any], **kwargs: Any) -> list[Any]:
    """The published API reference (/api/openapi.json) documents the user API only.

    The admin console's endpoints describe how detection is configured, which users must not
    learn; the web app's contract (manage.py spectacular) still includes them.
    """
    return [e for e in endpoints if not e[0].startswith(ADMIN_PREFIX)]


def require_response_fields(result: dict[str, Any], generator: Any, request: Any, public: bool) -> dict[str, Any]:
    """Serializers always render every declared field, so response schemas list them all as required.

    Request components (suffix "Request", from COMPONENT_SPLIT_REQUEST) keep their real requiredness.
    Nullability is expressed separately (`nullable: true`), so required + nullable stays accurate.
    """
    for name, component in result.get("components", {}).get("schemas", {}).items():
        if name.endswith("Request") or component.get("type") != "object" or "properties" not in component:
            continue
        optional = OPTIONAL_RESPONSE_FIELDS.get(name, set())
        component["required"] = sorted(p for p in component["properties"] if p not in optional)
    return result
