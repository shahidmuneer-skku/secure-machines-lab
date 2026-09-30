"""The Django admin, hardened: superusers with a two-factor-verified session only.

Django's own admin login takes a password and nothing else, which would bypass the MFA
that every staff role requires (and allauth's rate limits). This site has no login form:
people sign in through the app (password + 2FA) and the shared session opens the admin.
"""

from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def mfa_verified(request: HttpRequest) -> bool:
    from allauth.account.authentication import get_authentication_records

    return any(record.get("method") == "mfa" for record in get_authentication_records(request))


class SecureAdminSite(admin.AdminSite):
    site_header = "Secure Machines Lab · data admin"
    site_title = "SML data admin"
    index_title = "Raw data (superusers only)"

    def has_permission(self, request: HttpRequest) -> bool:
        user = request.user
        return bool(user.is_active and user.is_superuser and mfa_verified(request))

    def login(self, request: HttpRequest, extra_context: dict | None = None) -> HttpResponse:
        index = reverse("admin:index", current_app=self.name)
        target = request.GET.get("next") or index
        if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            target = index
        if self.has_permission(request):
            return HttpResponseRedirect(target)
        if request.user.is_authenticated:
            return HttpResponseForbidden(
                "The data admin is limited to superusers whose current session was verified with "
                "two-factor authentication. Sign out, then sign in again with your second factor.",
                content_type="text/plain; charset=utf-8",
            )
        return HttpResponseRedirect(f"{settings.PUBLIC_WEB_URL}/login?next={quote(target, safe='')}")
