from __future__ import annotations

from django.conf import settings

from sml.core.exceptions import ApiError

from .base import PaymentProvider
from .mock import MockProvider
from .stripe_provider import StripeProvider
from .toss import TossProvider

_REGISTRY: dict[str, type] = {"toss": TossProvider, "stripe": StripeProvider, "mock": MockProvider}
CURRENCY = {"toss": "KRW", "stripe": "USD", "mock": "USD"}


class ProviderUnavailable(ApiError):
    status_code = 503
    default_code = "PAYMENT_PROVIDER_UNAVAILABLE"
    default_detail = "This payment method is not available right now."
    title = "Payment provider unavailable"


def enabled_providers() -> list[str]:
    if not settings.BILLING_ENABLED:
        return []
    names = list(settings.BILLING_PROVIDERS)
    if settings.DEBUG and "mock" not in names:
        names.append("mock")
    return [n for n in names if n in _REGISTRY and _REGISTRY[n]().is_configured()]


def get_provider(name: str) -> PaymentProvider:
    if name not in enabled_providers():
        raise ProviderUnavailable()
    return _REGISTRY[name]()
