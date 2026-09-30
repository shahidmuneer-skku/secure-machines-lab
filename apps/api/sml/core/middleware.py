"""Request-scoped middleware: request IDs and security headers."""

from __future__ import annotations

import contextvars
import re
import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def current_request_id() -> str:
    return _request_id.get()


def client_ip(request: HttpRequest | None) -> str | None:
    """Client IP. Behind nginx, the proxy sets X-Real-IP (never trust a client-supplied XFF chain)."""
    if request is None:
        return None
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        real = request.META.get("HTTP_X_REAL_IP")
        if real:
            return real.strip()
    return request.META.get("REMOTE_ADDR")


class RequestIdMiddleware:
    """Accepts a well-formed inbound X-Request-ID or generates one, and echoes it back."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        inbound = request.META.get("HTTP_X_REQUEST_ID", "")
        rid = inbound if _SAFE_REQUEST_ID.match(inbound) else uuid.uuid4().hex
        token = _request_id.set(rid)
        request.request_id = rid  # type: ignore[attr-defined]
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware:
    """Headers Django doesn't set itself. The API only serves JSON, so its CSP is maximally strict."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        path = request.path
        is_docs = path.startswith(("/api/docs", "/api/django-admin", "/api/static"))
        if not is_docs:
            response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if path.startswith("/api/") and "Cache-Control" not in response:
            response["Cache-Control"] = "no-store"
        return response
