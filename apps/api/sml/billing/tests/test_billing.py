"""Payments: verified fulfilment, webhook idempotency, amount checks and the refund policy."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import time_machine
from django.utils import timezone

from sml.billing import services
from sml.billing.models import CreditPack, Payment, Plan, Refund, Subscription, WebhookEvent
from sml.billing.providers.base import CheckoutResult, ProviderEvent
from sml.core.exceptions import ApiError, Conflict
from sml.credits import services as credits

pytestmark = pytest.mark.django_db


class FakeProvider:
    """Stands in for Stripe: returns whatever events the test queues, records refunds."""

    name = "stripe"
    events: list[ProviderEvent] = []
    refunds: list[tuple[str, int]] = []

    def is_configured(self) -> bool:
        return True

    def create_pack_checkout(self, payment: Any, **kw: Any) -> CheckoutResult:
        return CheckoutResult(self.name, redirect_url=f"https://checkout.example/{payment.order_id}")

    def create_subscription_checkout(self, payment: Any, subscription: Any, **kw: Any) -> CheckoutResult:
        return self.create_pack_checkout(payment)

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[ProviderEvent]:
        return list(self.events)

    def refund(self, payment: Any, amount: int, reason: str) -> str:
        self.refunds.append((payment.order_id, amount))
        return f"re_{payment.order_id}"

    def cancel_subscription(self, subscription: Any, *, at_period_end: bool) -> None:
        return None


@pytest.fixture(autouse=True)
def provider(monkeypatch: pytest.MonkeyPatch) -> type[FakeProvider]:
    FakeProvider.events, FakeProvider.refunds = [], []
    monkeypatch.setattr(services, "get_provider", lambda name: FakeProvider())
    return FakeProvider


def pack(slug: str = "starter") -> CreditPack:
    return CreditPack.objects.get(slug=slug)


def paid_event(payment: Payment, event_id: str = "evt_1", amount: int | None = None) -> ProviderEvent:
    return ProviderEvent(event_id, "payment.paid", order_id=payment.order_id, provider_payment_id="pi_1",
                         amount=payment.amount if amount is None else amount, currency=payment.currency)


def buy(user, provider, slug: str = "starter") -> Payment:  # type: ignore[no-untyped-def]
    payment, checkout = services.start_pack_checkout(user, pack(slug), "stripe")
    assert checkout.redirect_url.endswith(payment.order_id)
    provider.events = [paid_event(payment)]
    services.handle_webhook("stripe", b"{}", {})
    payment.refresh_from_db()
    return payment


def test_checkout_prices_come_from_the_server(user):
    payment, _ = services.start_pack_checkout(user, pack("standard"), "stripe")
    assert (payment.amount, payment.currency, payment.credits) == (4_500, "USD", 500)
    assert payment.status == Payment.Status.PENDING


def test_paid_webhook_grants_credits_exactly_once(user, provider):
    payment = buy(user, provider)
    assert payment.status == Payment.Status.PAID
    assert credits.get_balance(user).balance == 100
    # The same delivery again, and a different event for the same order: no double grant.
    services.handle_webhook("stripe", b"{}", {})
    provider.events = [paid_event(payment, "evt_2")]
    services.handle_webhook("stripe", b"{}", {})
    assert credits.get_balance(user).balance == 100
    assert WebhookEvent.objects.filter(provider="stripe").count() == 2


def test_amount_mismatch_is_flagged_and_grants_nothing(user, provider):
    payment, _ = services.start_pack_checkout(user, pack(), "stripe")
    provider.events = [paid_event(payment, amount=1)]
    services.handle_webhook("stripe", b"{}", {})
    payment.refresh_from_db()
    assert payment.status == Payment.Status.FAILED
    assert credits.get_balance(user).balance == 0
    assert "did not match" in WebhookEvent.objects.get(event_id="evt_1").error


def test_purchased_credits_expire_after_the_configured_period(user, provider, platform):
    platform.purchased_credit_expiry_days = 365
    platform.save()
    buy(user, provider)
    with time_machine.travel(timezone.now() + timedelta(days=366)):
        assert credits.get_balance(user).balance == 0


def test_unused_pack_refund_is_full_within_30_days(user, provider, make_user):
    payment = buy(user, provider)
    quote = services.refund_quote(payment)
    assert quote.eligible and quote.amount == payment.amount
    refund = services.refund_payment(payment, actor=make_user(roles=("billing_admin",)), reason="customer request")
    assert refund.status == Refund.Status.SUCCEEDED and refund.credits_revoked == 100
    assert provider.refunds == [(payment.order_id, payment.amount)]
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REFUNDED
    assert credits.get_balance(user).balance == 0
    assert credits.verify_wallet(credits.ensure_wallet(user))


def test_partly_used_pack_is_refunded_pro_rata(user, provider):
    payment = buy(user, provider)
    credits.capture(credits.reserve(user, 40, reference_type="job", reference_id="j"))
    quote = services.refund_quote(payment)
    assert quote.amount == payment.amount * 60 // 100


def test_pack_refund_window_closes_after_30_days(user, provider):
    payment = buy(user, provider)
    with time_machine.travel(timezone.now() + timedelta(days=31)):
        assert not services.refund_quote(payment).eligible
        with pytest.raises(Conflict):
            services.refund_payment(payment, actor=None, reason="late")
        # Company fault overrides the policy.
        assert services.refund_quote(payment, override_full=True).amount == payment.amount


def test_subscription_refund_full_within_7_days_if_unused_else_pro_rata(user, provider):
    plan = Plan.objects.get(slug="basic")
    payment, _ = services.start_subscription_checkout(user, plan, "stripe")
    sub = payment.subscription
    sub.provider_subscription_id = "sub_1"
    sub.save()
    services.fulfil_payment(payment, services.VerifiedPayment("in_1", payment.amount, payment.currency))
    payment.refresh_from_db()
    assert Subscription.objects.get(pk=sub.pk).status == Subscription.Status.ACTIVE
    assert credits.get_balance(user).balance == plan.monthly_credits
    assert services.refund_quote(payment).amount == payment.amount
    credits.capture(credits.reserve(user, 1, reference_type="job", reference_id="j"))
    with time_machine.travel(timezone.now() + timedelta(days=10)):
        quote = services.refund_quote(payment)
        assert 0 < quote.amount < payment.amount


def test_unknown_provider_is_rejected(monkeypatch, user):
    monkeypatch.undo()
    with pytest.raises(ApiError):
        services.start_pack_checkout(user, pack(), "paypal")
