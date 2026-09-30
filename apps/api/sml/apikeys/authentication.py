"""DRF authentication for `Authorization: Bearer sml_<env>_<prefix>_<secret>`."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import authentication, exceptions
from rest_framework.request import Request

from sml.core.middleware import client_ip
from sml.core.models import PlatformSettings

from .models import ApiKey
from .services import verify

TOUCH_INTERVAL = timedelta(seconds=60)


class ApiKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request: Request) -> tuple | None:
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        parts = header.split(" ", 1)
        if len(parts) != 2 or parts[0] != self.keyword or not parts[1].startswith("sml_"):
            return None
        key = verify(parts[1])
        if key is None:
            raise exceptions.AuthenticationFailed("Invalid, expired or revoked API key.")
        user = key.user
        if not user.is_active:
            raise exceptions.AuthenticationFailed("The account that owns this API key is disabled.")
        ip = client_ip(request._request)
        if not key.ip_allowed(ip):
            raise exceptions.AuthenticationFailed("This API key is not allowed from your IP address.")
        if PlatformSettings.load().api_access_requires_plan and not _has_api_plan(user):
            raise exceptions.PermissionDenied("Your plan does not include API access.")
        now = timezone.now()
        if key.last_used_at is None or now - key.last_used_at > TOUCH_INTERVAL:
            ApiKey.objects.filter(pk=key.pk).update(last_used_at=now, last_used_ip=ip)
        request._request.sml_api_key = key  # type: ignore[attr-defined]
        return user, key

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="api"'


def _has_api_plan(user) -> bool:  # type: ignore[no-untyped-def]
    return user.subscriptions.filter(status__in=["active", "past_due"], plan__api_access=True).exists()
