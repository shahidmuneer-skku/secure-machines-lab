"""RFC 9457 Problem Details for every API error, with stable machine-readable codes."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .middleware import current_request_id

logger = logging.getLogger(__name__)

PROBLEM_BASE = "https://securemachineslab.com/docs/errors#"


class ApiError(exceptions.APIException):
    """Base for domain errors. Subclasses set `status_code`, `default_code`, `default_detail`."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BAD_REQUEST"
    default_detail = "The request could not be processed."
    title = "Bad request"

    def __init__(self, detail: str | None = None, *, extra: dict[str, Any] | None = None):
        super().__init__(detail or self.default_detail, self.default_code)
        self.extra = extra or {}


class InsufficientCredits(ApiError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_code = "INSUFFICIENT_CREDITS"
    default_detail = "Not enough credits for this request."
    title = "Insufficient credits"


class ModelNotAllowed(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "MODEL_NOT_ALLOWED"
    default_detail = "One or more selected models are not available to your account."
    title = "Model not allowed"


class ModuleNotAllowed(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "MODULE_NOT_ALLOWED"
    default_detail = "This detection module is not available to your account."
    title = "Module not allowed"


class InvalidMedia(ApiError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "INVALID_MEDIA"
    default_detail = "The uploaded file is not a supported image or video."
    title = "Invalid media"


class Conflict(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "CONFLICT"
    default_detail = "The resource is not in a state that allows this action."
    title = "Conflict"


class IdempotencyConflict(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_KEY_REUSED"
    default_detail = "This Idempotency-Key was already used with a different request."
    title = "Idempotency key reused"


class MfaRequired(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "MFA_REQUIRED"
    default_detail = "This action requires a session verified with two-factor authentication."
    title = "Two-factor authentication required"


class TrialExhausted(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "TRIAL_EXHAUSTED"
    default_detail = "You have used today's free trial. Create a free account to get more credits."
    title = "Trial limit reached"


class ServiceUnavailable(ApiError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "SERVICE_UNAVAILABLE"
    default_detail = "The service is temporarily unavailable."
    title = "Service unavailable"


class ProviderError(ApiError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "PAYMENT_PROVIDER_ERROR"
    default_detail = "The payment provider returned an error."
    title = "Payment provider error"


_DEFAULT_CODES = {
    400: ("VALIDATION_ERROR", "Validation error"),
    401: ("NOT_AUTHENTICATED", "Authentication required"),
    403: ("PERMISSION_DENIED", "Permission denied"),
    404: ("NOT_FOUND", "Not found"),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed"),
    406: ("NOT_ACCEPTABLE", "Not acceptable"),
    409: ("CONFLICT", "Conflict"),
    413: ("PAYLOAD_TOO_LARGE", "Payload too large"),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Unsupported media type"),
    429: ("RATE_LIMITED", "Too many requests"),
}


def _flatten_errors(data: Any, prefix: str = "") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            errors.extend(_flatten_errors(value, path))
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            if isinstance(value, (dict, list)):
                errors.extend(_flatten_errors(value, f"{prefix}[{idx}]"))
            else:
                errors.append({"field": prefix or "non_field_errors", "message": str(value)})
    else:
        errors.append({"field": prefix or "non_field_errors", "message": str(data)})
    return errors


def problem_response(
    status_code: int, code: str, title: str, detail: str, *, errors: list | None = None, **extra: Any
) -> Response:
    body: dict[str, Any] = {
        "type": PROBLEM_BASE + code.lower(),
        "title": title,
        "status": status_code,
        "detail": detail,
        "code": code,
        "request_id": current_request_id(),
    }
    if errors:
        body["errors"] = errors
    body.update(extra)
    return Response(body, status=status_code, content_type="application/problem+json")


def problem_exception_handler(exc: Exception, context: dict) -> Response | None:
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return problem_response(500, "INTERNAL_ERROR", "Internal server error",
                                "An unexpected error occurred. Quote the request_id when contacting support.")

    status_code = response.status_code
    default_code, default_title = _DEFAULT_CODES.get(status_code, ("ERROR", "Error"))
    headers = {k: v for k, v in response.items() if k in ("Retry-After", "WWW-Authenticate")}

    if isinstance(exc, ApiError):
        result = problem_response(status_code, exc.default_code, exc.title, str(exc.detail), **exc.extra)
    elif isinstance(exc, exceptions.ValidationError):
        result = problem_response(status_code, default_code, default_title,
                                  "One or more fields are invalid.", errors=_flatten_errors(exc.detail))
    else:
        detail = exc.detail if isinstance(exc, exceptions.APIException) else str(exc)
        if isinstance(detail, (list, dict)):
            result = problem_response(status_code, default_code, default_title, default_title,
                                      errors=_flatten_errors(detail))
        else:
            code = default_code
            if isinstance(exc, exceptions.Throttled):
                code = "RATE_LIMITED"
            result = problem_response(status_code, code, default_title, str(detail))
    for key, value in headers.items():
        result[key] = value
    return result
