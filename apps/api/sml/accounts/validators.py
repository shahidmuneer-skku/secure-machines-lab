"""Rejects passwords found in known breaches via HIBP's k-anonymity range API.

Only the first five hex chars of the SHA-1 hash leave the server. If the service
is unreachable the check is skipped (fail open) so signups aren't blocked.
"""

from __future__ import annotations

import hashlib
import logging

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class BreachedPasswordValidator:
    def validate(self, password: str, user=None) -> None:  # type: ignore[no-untyped-def]
        if not getattr(settings, "BREACHED_PASSWORD_CHECK", True):
            return
        digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        try:
            resp = httpx.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"Add-Padding": "true", "User-Agent": "sml-password-check"},
                timeout=3.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.info("HIBP check unavailable; skipping")
            return
        for line in resp.text.splitlines():
            candidate, _sep, count = line.partition(":")
            if candidate == suffix and int(count or 0) > 0:
                raise ValidationError(
                    _("This password has appeared in a data breach. Please choose a different one."),
                    code="password_breached",
                )

    def get_help_text(self) -> str:
        return _("Your password must not appear in known data breaches.")
