from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest

from sml.core.models import PlatformSettings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return PlatformSettings.load().signups_enabled

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        return "/app"
