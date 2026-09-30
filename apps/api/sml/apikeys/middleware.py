"""Records per-key request logs and daily usage counters."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from sml.core.middleware import client_ip, current_request_id

from .models import ApiRequestLog
from .services import bump_usage

logger = logging.getLogger(__name__)


class ApiKeyUsageMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = time.monotonic()
        response = self.get_response(request)
        key = getattr(request, "sml_api_key", None)
        if key is not None:
            try:
                ApiRequestLog.objects.create(
                    api_key=key, method=request.method or "", path=request.path[:255],
                    status=response.status_code, duration_ms=int((time.monotonic() - started) * 1000),
                    ip=client_ip(request), request_id=current_request_id(),
                )
                bump_usage(key, requests=1, errors=1 if response.status_code >= 400 else 0)
            except Exception:  # noqa: BLE001 - usage logging must never break a request
                logger.warning("Failed to record API key usage", exc_info=True)
        return response
