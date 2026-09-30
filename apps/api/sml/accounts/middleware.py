"""Idle and absolute session timeouts.

- Without "remember me": 30 min idle (sliding), 12 h absolute.
- With "remember me": 30 days absolute, no idle timeout.
Values come from settings (SESSION_IDLE_TIMEOUT, SESSION_ABSOLUTE_TIMEOUT, SESSION_REMEMBER_TIMEOUT).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse

AUTH_AT = "sml_auth_at"
LAST_SEEN = "sml_last_seen"
REMEMBER = "sml_remember"


class SessionTimeoutMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and hasattr(request, "session"):
            now = int(time.time())
            session = request.session
            auth_at = session.get(AUTH_AT)
            if auth_at is None:
                session[AUTH_AT] = auth_at = now
                session[REMEMBER] = not session.get_expire_at_browser_close()
            remember = bool(session.get(REMEMBER))
            last_seen = int(session.get(LAST_SEEN, now))
            absolute = settings.SESSION_REMEMBER_TIMEOUT if remember else settings.SESSION_ABSOLUTE_TIMEOUT
            idle_expired = (not remember) and now - last_seen > settings.SESSION_IDLE_TIMEOUT
            if idle_expired or now - int(auth_at) > absolute:
                logout(request)
            elif now - last_seen > 60:
                # Throttle session writes to once a minute.
                session[LAST_SEEN] = now
        return self.get_response(request)
