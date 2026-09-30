"""Idempotency-Key support for POSTs that create jobs, reserve credits, or start payments.

A repeated request with the same key and body returns the stored response; the
same key with a different body is rejected with 409 IDEMPOTENCY_KEY_REUSED.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from .exceptions import ApiError, IdempotencyConflict
from .models import IdempotencyRecord

HEADER = "HTTP_IDEMPOTENCY_KEY"
TTL = timedelta(hours=24)


class IdempotencyKeyRequired(ApiError):
    default_code = "IDEMPOTENCY_KEY_REQUIRED"
    default_detail = "Send an Idempotency-Key header (e.g. a UUID) with this request."
    title = "Idempotency key required"


def _principal(request: Request) -> str:
    auth = getattr(request, "auth", None)
    if auth is not None and hasattr(auth, "prefix"):
        return f"key:{auth.prefix}"
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    return f"anon:{request.COOKIES.get('sml_trial', '')}"


def _fingerprint(request: Request) -> str:
    try:
        body: Any = request.data
        if hasattr(body, "dict"):
            body = {k: v for k, v in body.items() if not hasattr(v, "read")}
        raw = json.dumps(body, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        raw = ""
    return hashlib.sha256(f"{request.method}:{request.path}:{raw}".encode()).hexdigest()


def idempotent(required: bool = True) -> Callable:
    def decorator(view_method: Callable) -> Callable:
        @wraps(view_method)
        def wrapper(self: Any, request: Request, *args: Any, **kwargs: Any) -> Response:
            key = request.META.get(HEADER, "").strip()
            if not key:
                if required:
                    raise IdempotencyKeyRequired()
                return view_method(self, request, *args, **kwargs)
            if len(key) > 128:
                raise IdempotencyKeyRequired("Idempotency-Key must be at most 128 characters.")
            principal = _principal(request)
            fingerprint = _fingerprint(request)
            IdempotencyRecord.objects.filter(
                principal=principal, key=key, created_at__lt=timezone.now() - TTL
            ).delete()
            existing = IdempotencyRecord.objects.filter(
                principal=principal, key=key, created_at__gte=timezone.now() - TTL
            ).first()
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    raise IdempotencyConflict()
                if existing.response_status:
                    resp = Response(existing.response_body, status=existing.response_status)
                    resp["Idempotent-Replayed"] = "true"
                    return resp
                raise IdempotencyConflict("A request with this Idempotency-Key is still being processed.")
            try:
                with transaction.atomic():
                    record = IdempotencyRecord.objects.create(
                        principal=principal, key=key, fingerprint=fingerprint
                    )
            except IntegrityError as exc:
                raise IdempotencyConflict("A request with this Idempotency-Key is still being processed.") from exc
            try:
                response = view_method(self, request, *args, **kwargs)
            except Exception:
                record.delete()
                raise
            if 200 <= response.status_code < 300:
                record.response_status = response.status_code
                record.response_body = response.data
                record.save(update_fields=["response_status", "response_body"])
            else:
                record.delete()
            return response

        return wrapper

    return decorator
