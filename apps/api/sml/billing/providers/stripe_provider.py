"""Stripe adapter: hosted Checkout for packs and subscriptions, verified webhooks, refunds, portal."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import stripe
from django.conf import settings

from sml.core.exceptions import ProviderError

from ..models import BillingCustomer, localized
from .base import CheckoutResult, ProviderEvent


def _ts(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), UTC) if value else None


class StripeProvider:
    name = "stripe"

    def __init__(self) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.max_network_retries = 2

    def is_configured(self) -> bool:
        return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET)

    def _customer(self, user: Any) -> str:
        cust, _ = BillingCustomer.objects.get_or_create(user=user)
        if not cust.stripe_customer_id:
            created = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.pk)})
            cust.stripe_customer_id = created.id
            cust.save(update_fields=["stripe_customer_id"])
        return cust.stripe_customer_id

    def create_pack_checkout(self, payment: Any, *, success_url: str, cancel_url: str) -> CheckoutResult:
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer=self._customer(payment.user),
                client_reference_id=payment.order_id,
                line_items=[{"quantity": 1, "price_data": {
                    "currency": "usd", "unit_amount": payment.amount,
                    "product_data": {"name": payment.order_name}}}],
                metadata={"order_id": payment.order_id},
                payment_intent_data={"metadata": {"order_id": payment.order_id}},
                success_url=success_url, cancel_url=cancel_url,
                locale={"ko": "ko", "de": "de"}.get(payment.user.locale, "en"),
            )
        except stripe.StripeError as exc:
            raise ProviderError(str(exc.user_message or "Stripe checkout could not be created.")) from exc
        payment.provider_session_id = session.id
        payment.save(update_fields=["provider_session_id", "updated_at"])
        return CheckoutResult(self.name, redirect_url=session.url)

    def create_subscription_checkout(self, payment: Any, subscription: Any, *, success_url: str,
                                     cancel_url: str) -> CheckoutResult:
        plan = subscription.plan
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=self._customer(payment.user),
                client_reference_id=payment.order_id,
                line_items=[{"quantity": 1, "price_data": {
                    "currency": "usd", "unit_amount": payment.amount, "recurring": {"interval": "month"},
                    "product_data": {"name": localized(plan.name, "en")}}}],
                metadata={"order_id": payment.order_id, "subscription_id": str(subscription.pk)},
                subscription_data={"metadata": {"order_id": payment.order_id,
                                                "subscription_id": str(subscription.pk)}},
                success_url=success_url, cancel_url=cancel_url,
                locale={"ko": "ko", "de": "de"}.get(payment.user.locale, "en"),
            )
        except stripe.StripeError as exc:
            raise ProviderError(str(exc.user_message or "Stripe checkout could not be created.")) from exc
        payment.provider_session_id = session.id
        payment.save(update_fields=["provider_session_id", "updated_at"])
        return CheckoutResult(self.name, redirect_url=session.url)

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[ProviderEvent]:
        sig = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(body, sig, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise ProviderError("Invalid Stripe signature.") from exc
        obj = event["data"]["object"]
        etype = event["type"]
        if etype == "checkout.session.completed":
            # Re-fetch from the API: never trust the webhook body for amounts.
            session = stripe.checkout.Session.retrieve(obj["id"])
            if session.mode == "payment" and session.payment_status == "paid":
                return [ProviderEvent(event.id, "payment.paid", order_id=session.metadata.get("order_id", ""),
                                      provider_payment_id=session.payment_intent or "",
                                      amount=int(session.amount_total or 0), currency=(session.currency or "").upper(),
                                      raw=dict(session))]
            if session.mode == "subscription":
                return [ProviderEvent(event.id, "subscription.linked", order_id=session.metadata.get("order_id", ""),
                                      provider_subscription_id=session.subscription or "", raw=dict(session))]
            return []
        if etype == "invoice.paid":
            invoice = stripe.Invoice.retrieve(obj["id"])
            line = invoice.lines.data[0] if invoice.lines and invoice.lines.data else None
            sub_id = invoice.get("subscription") or (
                (invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription", "")
            return [ProviderEvent(event.id, "invoice.paid", provider_payment_id=invoice.id,
                                  provider_subscription_id=sub_id or "", amount=int(invoice.amount_paid or 0),
                                  currency=(invoice.currency or "").upper(),
                                  period_start=_ts(line.period.start) if line else None,
                                  period_end=_ts(line.period.end) if line else None,
                                  receipt_url=invoice.hosted_invoice_url or "", raw=dict(invoice))]
        if etype in ("customer.subscription.updated", "customer.subscription.deleted"):
            return [ProviderEvent(event.id, "subscription.updated", provider_subscription_id=obj["id"],
                                  status=obj.get("status", ""), cancel_at_period_end=obj.get("cancel_at_period_end"),
                                  raw=dict(obj))]
        if etype == "invoice.payment_failed":
            return [ProviderEvent(event.id, "subscription.updated",
                                  provider_subscription_id=obj.get("subscription") or "", status="past_due", raw=obj)]
        if etype == "charge.refunded":
            return [ProviderEvent(event.id, "payment.refunded", provider_payment_id=obj.get("payment_intent") or "",
                                  amount=int(obj.get("amount_refunded") or 0), raw=obj)]
        return []

    def refund(self, payment: Any, amount: int, reason: str) -> str:
        try:
            if payment.kind == "pack":
                refund = stripe.Refund.create(payment_intent=payment.provider_payment_id, amount=amount,
                                              metadata={"reason": reason[:400]})
            else:
                invoice = stripe.Invoice.retrieve(payment.provider_payment_id, expand=["payments"])
                pi = None
                payments = getattr(invoice, "payments", None)
                if payments and payments.data:
                    pi = payments.data[0].payment.payment_intent
                pi = pi or invoice.get("payment_intent")
                refund = stripe.Refund.create(payment_intent=pi, amount=amount, metadata={"reason": reason[:400]})
        except stripe.StripeError as exc:
            raise ProviderError(str(exc.user_message or "Stripe refund failed.")) from exc
        return refund.id

    def cancel_subscription(self, subscription: Any, *, at_period_end: bool) -> None:
        try:
            if at_period_end:
                stripe.Subscription.modify(subscription.provider_subscription_id, cancel_at_period_end=True)
            else:
                stripe.Subscription.cancel(subscription.provider_subscription_id)
        except stripe.StripeError as exc:
            raise ProviderError(str(exc.user_message or "Stripe subscription update failed.")) from exc

    def resume_subscription(self, subscription: Any) -> None:
        stripe.Subscription.modify(subscription.provider_subscription_id, cancel_at_period_end=False)

    def portal_url(self, user: Any, return_url: str) -> str | None:
        cust = BillingCustomer.objects.filter(user=user).exclude(stripe_customer_id="").first()
        if cust is None:
            return None
        session = stripe.billing_portal.Session.create(customer=cust.stripe_customer_id, return_url=return_url)
        return session.url
