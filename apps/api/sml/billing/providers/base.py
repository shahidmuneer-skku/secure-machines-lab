"""Provider-agnostic payment interface (ADR 0007).

Rules every adapter follows:
  * hosted checkout / provider SDK only — we never see card data (PCI SAQ-A)
  * credits are granted only after the provider confirms the payment
    server-to-server (Toss confirm API, verified Stripe webhook + re-fetch)
  * amounts are always re-checked against our own Payment row
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class CheckoutResult:
    provider: str
    redirect_url: str | None = None
    # Parameters for the provider's browser SDK (Toss) when there is no redirect URL.
    client_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedPayment:
    provider_payment_id: str
    amount: int
    currency: str
    method: str = ""
    receipt_url: str = ""
    paid_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderEvent:
    """Normalized webhook event."""

    event_id: str
    type: str  # payment.paid | payment.failed | payment.refunded | subscription.updated | invoice.paid
    order_id: str = ""
    provider_payment_id: str = ""
    provider_subscription_id: str = ""
    amount: int = 0
    currency: str = ""
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: str = ""
    cancel_at_period_end: bool | None = None
    receipt_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def create_pack_checkout(self, payment: Any, *, success_url: str, cancel_url: str) -> CheckoutResult: ...

    def create_subscription_checkout(self, payment: Any, subscription: Any, *, success_url: str,
                                     cancel_url: str) -> CheckoutResult: ...

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[ProviderEvent]: ...

    def refund(self, payment: Any, amount: int, reason: str) -> str: ...

    def cancel_subscription(self, subscription: Any, *, at_period_end: bool) -> None: ...

    def portal_url(self, user: Any, return_url: str) -> str | None: ...
