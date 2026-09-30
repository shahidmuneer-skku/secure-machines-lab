"""Cloudflare Turnstile verification. Disabled (always passes) when no secret is configured."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def captcha_enabled() -> bool:
    return bool(settings.TURNSTILE_SECRET_KEY)


def verify_captcha(token: str | None, remote_ip: str | None = None) -> bool:
    if not captcha_enabled():
        return True
    if not token:
        return False
    try:
        resp = httpx.post(
            VERIFY_URL,
            data={"secret": settings.TURNSTILE_SECRET_KEY, "response": token, "remoteip": remote_ip or ""},
            timeout=5.0,
        )
        return bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile verification failed", exc_info=True)
        return False
