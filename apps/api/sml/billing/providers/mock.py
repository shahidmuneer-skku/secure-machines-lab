"""Development-only provider: completes payments locally (enabled only with DEBUG=True)."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from .base import CheckoutResult, ProviderEvent


class MockProvider:
    name = "mock"

    def is_configured(self) -> bool:
        return bool(settings.DEBUG)

    def create_pack_checkout(self, payment: Any, *, success_url: str, cancel_url: str) -> CheckoutResult:
        return CheckoutResult(self.name, redirect_url=f"{settings.PUBLIC_WEB_URL}/app/billing/mock-checkout"
                                                      f"?order={payment.order_id}")

    def create_subscription_checkout(self, payment: Any, subscription: Any, *, success_url: str,
                                     cancel_url: str) -> CheckoutResult:
        return self.create_pack_checkout(payment, success_url=success_url, cancel_url=cancel_url)

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[ProviderEvent]:
        return []

    def refund(self, payment: Any, amount: int, reason: str) -> str:
        return f"mock-refund-{payment.order_id}"

    def cancel_subscription(self, subscription: Any, *, at_period_end: bool) -> None:
        return None

    def portal_url(self, user: Any, return_url: str) -> str | None:
        return None
