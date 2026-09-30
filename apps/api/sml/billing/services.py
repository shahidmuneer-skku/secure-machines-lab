"""Checkout, fulfilment (credit grants), subscriptions and refunds.

Refund policy (owner-approved, see /refund-policy):
  * Credit packs: unused *paid* credits are refundable within 30 days of purchase,
    pro-rata: amount_paid × remaining_paid / purchased_paid. Bonus credits never.
  * Subscriptions: full refund within 7 days if none of that period's credits
    were used; otherwise pro-rata by days remaining in the period.
  * Payment errors / service failure on our side: full refund (admin override).
"""

from __future__ import annotations

import calendar
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from sml.core import audit
from sml.core.events import publish_to_user
from sml.core.exceptions import ApiError, Conflict
from sml.core.models import PlatformSettings
from sml.credits import services as credits
from sml.credits.models import CreditBucket, CreditSource, LedgerKind

from .models import CreditPack, Currency, Payment, Plan, Refund, Subscription, WebhookEvent, localized
from .providers import CURRENCY, get_provider
from .providers.base import CheckoutResult, ProviderEvent, VerifiedPayment

logger = logging.getLogger(__name__)

PACK_REFUND_WINDOW = timedelta(days=30)
SUBSCRIPTION_WITHDRAWAL_WINDOW = timedelta(days=7)


def new_order_id() -> str:
    return f"sml_{timezone.now():%Y%m%d}_{secrets.token_hex(8)}"


def add_month(dt: datetime) -> datetime:
    month = dt.month % 12 + 1
    year = dt.year + (dt.month // 12)
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _urls(kind: str, provider: str, order_id: str) -> tuple[str, str]:
    base = f"{settings.PUBLIC_WEB_URL}/app/billing/return?provider={provider}&kind={kind}&order={order_id}"
    return f"{base}&status=success", f"{base}&status=cancel"


# --- checkout ---------------------------------------------------------------------

def start_pack_checkout(user: Any, pack: CreditPack, provider_name: str) -> tuple[Payment, CheckoutResult]:
    if not pack.active:
        raise Conflict("This credit pack is no longer available.")
    provider = get_provider(provider_name)
    currency = CURRENCY[provider_name]
    name = localized(pack.name, user.locale)
    payment = Payment.objects.create(
        user=user, provider=provider_name, kind=Payment.Kind.PACK, order_id=new_order_id(),
        order_name=f"{name} ({pack.credits:,} credits)"[:128], currency=currency, amount=pack.price_for(currency),
        pack=pack, credits=pack.credits, bonus_credits=pack.bonus_credits,
    )
    success, cancel = _urls("pack", provider_name, payment.order_id)
    return payment, provider.create_pack_checkout(payment, success_url=success, cancel_url=cancel)


def start_subscription_checkout(user: Any, plan: Plan, provider_name: str) -> tuple[Payment, CheckoutResult]:
    if not plan.active:
        raise Conflict("This plan is no longer available.")
    if Subscription.objects.filter(user=user, status__in=[Subscription.Status.ACTIVE,
                                                         Subscription.Status.PAST_DUE]).exists():
        raise Conflict("You already have an active subscription. Cancel it before switching plans.")
    provider = get_provider(provider_name)
    currency = CURRENCY[provider_name]
    sub = Subscription.objects.create(user=user, plan=plan, provider=provider_name, currency=currency)
    payment = Payment.objects.create(
        user=user, provider=provider_name, kind=Payment.Kind.SUBSCRIPTION, order_id=new_order_id(),
        order_name=f"{localized(plan.name, user.locale)} — monthly"[:128], currency=currency,
        amount=plan.price_for(currency), plan=plan, subscription=sub, credits=plan.monthly_credits,
    )
    success, cancel = _urls("subscription", provider_name, payment.order_id)
    return payment, provider.create_subscription_checkout(payment, sub, success_url=success, cancel_url=cancel)


# --- fulfilment ------------------------------------------------------------------------

def _purchase_expiry(pack: CreditPack | None) -> datetime | None:
    days = pack.credit_expiry_days if pack and pack.credit_expiry_days is not None else \
        PlatformSettings.load().purchased_credit_expiry_days
    return timezone.now() + timedelta(days=days) if days else None


class _AmountMismatch(Exception):
    pass


def fulfil_payment(payment: Payment, verified: VerifiedPayment) -> Payment:
    """Mark paid and grant credits. Idempotent; refuses amount/currency mismatches.

    Callers must not wrap this in their own transaction: a mismatch is flagged in a
    separate commit so the flag survives the error raised to the caller.
    """
    try:
        return _fulfil(payment, verified)
    except _AmountMismatch:
        _flag_amount_mismatch(payment, verified)
        raise ApiError("Payment amount did not match the order. Our team has been notified.") from None


def _flag_amount_mismatch(payment: Payment, verified: VerifiedPayment) -> None:
    logger.error("Amount mismatch for %s: expected %s %s, provider %s %s", payment.order_id, payment.amount,
                 payment.currency, verified.amount, verified.currency)
    with transaction.atomic():
        flagged = (Payment.objects.filter(pk=payment.pk).exclude(status=Payment.Status.PAID)
                   .update(status=Payment.Status.FAILED, failure_reason="Amount mismatch — flagged for review",
                           updated_at=timezone.now()))
        if flagged:
            audit.record("billing.amount_mismatch", target=payment,
                         after={"expected": payment.amount, "currency": payment.currency,
                                "received": verified.amount, "received_currency": verified.currency})


@transaction.atomic
def _fulfil(payment: Payment, verified: VerifiedPayment) -> Payment:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == Payment.Status.PAID:
        return payment
    if verified.amount != payment.amount or verified.currency.upper() != payment.currency:
        raise _AmountMismatch()
    now = timezone.now()
    payment.status = Payment.Status.PAID
    payment.provider_payment_id = verified.provider_payment_id or payment.provider_payment_id
    payment.method = verified.method[:64]
    payment.receipt_url = verified.receipt_url[:500]
    payment.paid_at = verified.paid_at or now
    payment.provider_data = verified.raw
    if payment.kind == Payment.Kind.PACK:
        payment.save()
        credits.grant(payment.user, payment.credits, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE,
                      expires_at=_purchase_expiry(payment.pack), payment=payment,
                      memo=payment.order_name, idempotency_key=f"payment:{payment.pk}")
        if payment.bonus_credits:
            credits.grant(payment.user, payment.bonus_credits, source=CreditSource.PROMO, kind=LedgerKind.PROMO,
                          expires_at=_purchase_expiry(payment.pack), payment=payment,
                          memo=f"Bonus: {payment.order_name}", idempotency_key=f"payment-bonus:{payment.pk}")
    else:
        sub = payment.subscription
        start = payment.period_start or now
        end = payment.period_end or add_month(start)
        payment.period_start, payment.period_end = start, end
        payment.save()
        if sub is not None:
            sub.status = Subscription.Status.ACTIVE
            sub.current_period_start, sub.current_period_end = start, end
            sub.failed_attempts = 0
            sub.save()
            credits.grant(payment.user, payment.credits, source=CreditSource.SUBSCRIPTION,
                          kind=LedgerKind.SUBSCRIPTION_GRANT, expires_at=end, payment=payment, subscription=sub,
                          memo=f"{localized(sub.plan.name, 'en')} {start:%Y-%m-%d}–{end:%Y-%m-%d}",
                          idempotency_key=f"payment:{payment.pk}")
    audit.record("billing.payment_paid", actor=payment.user, target=payment,
                 after={"amount": payment.amount, "currency": payment.currency})
    user_id = payment.user_id
    transaction.on_commit(lambda: publish_to_user(user_id, "billing.payment", {
        "order_id": payment.order_id, "status": payment.status}))
    return payment


def confirm_toss_payment(user: Any, *, payment_key: str, order_id: str, amount: int) -> Payment:
    payment = Payment.objects.filter(order_id=order_id, user=user, provider="toss", kind=Payment.Kind.PACK).first()
    if payment is None:
        raise ApiError("Unknown order.")
    if payment.status == Payment.Status.PAID:
        return payment
    if amount != payment.amount:
        raise ApiError("Amount does not match the order.")
    provider = get_provider("toss")
    verified = provider.confirm_payment(payment_key=payment_key, order_id=order_id, amount=payment.amount)
    return fulfil_payment(payment, verified)


def confirm_toss_billing(user: Any, *, auth_key: str, customer_key: str, order_id: str) -> Payment:
    payment = Payment.objects.filter(order_id=order_id, user=user, provider="toss",
                                     kind=Payment.Kind.SUBSCRIPTION).select_related("subscription").first()
    if payment is None or payment.subscription is None:
        raise ApiError("Unknown subscription order.")
    if payment.status == Payment.Status.PAID:
        return payment
    provider = get_provider("toss")
    if customer_key != provider._customer_key(user):
        raise ApiError("Customer key mismatch.")
    billing_key = provider.issue_billing_key(auth_key=auth_key, customer_key=customer_key)
    sub = payment.subscription
    sub.toss_billing_key = billing_key
    sub.save(update_fields=["toss_billing_key", "updated_at"])
    verified = provider.charge_billing_key(billing_key=billing_key, customer_key=customer_key,
                                           order_id=payment.order_id, order_name=payment.order_name,
                                           amount=payment.amount, email=user.email)
    return fulfil_payment(payment, verified)


def complete_mock_payment(user: Any, order_id: str) -> Payment:
    if not settings.DEBUG:
        raise ApiError("Mock payments are disabled.")
    payment = Payment.objects.get(order_id=order_id, user=user, provider="mock")
    return fulfil_payment(payment, VerifiedPayment(f"mock_{order_id}", payment.amount, payment.currency, "mock"))


# --- webhooks ----------------------------------------------------------------------------

def handle_webhook(provider_name: str, body: bytes, headers: dict[str, str]) -> int:
    provider = get_provider(provider_name)
    events = provider.parse_webhook(body, headers)
    processed = 0
    for ev in events:
        try:
            with transaction.atomic():
                record = WebhookEvent.objects.create(provider=provider_name, event_id=ev.event_id,
                                                     event_type=ev.type, payload=ev.raw)
        except IntegrityError:
            continue  # duplicate delivery
        try:
            _apply_event(provider_name, ev)
            record.processed_at = timezone.now()
        except Exception as exc:
            logger.exception("Webhook %s/%s failed", provider_name, ev.event_id)
            record.error = str(exc)[:2000]
        record.save(update_fields=["processed_at", "error"])
        processed += 1
    return processed


def _apply_event(provider_name: str, ev: ProviderEvent) -> None:
    if ev.type == "payment.paid" and ev.order_id:
        payment = Payment.objects.filter(order_id=ev.order_id, provider=provider_name).first()
        if payment and payment.kind == Payment.Kind.PACK:
            fulfil_payment(payment, VerifiedPayment(ev.provider_payment_id, ev.amount, ev.currency,
                                                    receipt_url=ev.receipt_url, raw={"event": ev.event_id}))
    elif ev.type == "subscription.linked":
        payment = Payment.objects.filter(order_id=ev.order_id, provider=provider_name).select_related(
            "subscription").first()
        if payment and payment.subscription:
            Subscription.objects.filter(pk=payment.subscription_id).update(
                provider_subscription_id=ev.provider_subscription_id)
    elif ev.type == "invoice.paid":
        sub = Subscription.objects.filter(provider=provider_name,
                                          provider_subscription_id=ev.provider_subscription_id).first()
        if sub is None:
            raise RuntimeError(f"Unknown subscription {ev.provider_subscription_id}")
        payment = (Payment.objects.filter(subscription=sub, kind=Payment.Kind.SUBSCRIPTION,
                                          status=Payment.Status.PENDING).first()
                   or Payment.objects.filter(provider_payment_id=ev.provider_payment_id).first())
        if payment is None:
            payment = Payment.objects.create(
                user=sub.user, provider=provider_name, kind=Payment.Kind.RENEWAL, order_id=new_order_id(),
                order_name=f"{localized(sub.plan.name, 'en')} — renewal", currency=sub.currency,
                amount=ev.amount, plan=sub.plan, subscription=sub, credits=sub.plan.monthly_credits)
        payment.period_start, payment.period_end = ev.period_start, ev.period_end
        payment.save(update_fields=["period_start", "period_end"])
        fulfil_payment(payment, VerifiedPayment(ev.provider_payment_id, ev.amount, ev.currency,
                                                receipt_url=ev.receipt_url))
    elif ev.type == "subscription.updated":
        sub = Subscription.objects.filter(provider=provider_name,
                                          provider_subscription_id=ev.provider_subscription_id).first()
        if sub is None:
            return
        mapping = {"active": Subscription.Status.ACTIVE, "trialing": Subscription.Status.ACTIVE,
                   "past_due": Subscription.Status.PAST_DUE, "unpaid": Subscription.Status.PAST_DUE,
                   "canceled": Subscription.Status.CANCELED, "incomplete_expired": Subscription.Status.EXPIRED}
        if ev.status in mapping:
            sub.status = mapping[ev.status]
        if ev.cancel_at_period_end is not None:
            sub.cancel_at_period_end = ev.cancel_at_period_end
        if sub.status == Subscription.Status.CANCELED and not sub.canceled_at:
            sub.canceled_at = timezone.now()
        sub.save()
    elif ev.type == "payment.refunded":
        payment = Payment.objects.filter(provider_payment_id=ev.provider_payment_id).first()
        if payment and ev.amount > payment.refunded_amount:
            payment.refunded_amount = ev.amount
            payment.status = (Payment.Status.REFUNDED if ev.amount >= payment.amount
                              else Payment.Status.PARTIALLY_REFUNDED)
            payment.save(update_fields=["refunded_amount", "status", "updated_at"])
    elif ev.type == "payment.failed" and ev.order_id:
        Payment.objects.filter(order_id=ev.order_id, status=Payment.Status.PENDING).update(
            status=Payment.Status.FAILED, failure_reason="Payment failed or expired")


# --- subscriptions -------------------------------------------------------------------------

def cancel_subscription(sub: Subscription, *, actor: Any, immediately: bool = False) -> Subscription:
    if not sub.is_live:
        raise Conflict("This subscription is not active.")
    get_provider(sub.provider).cancel_subscription(sub, at_period_end=not immediately)
    if immediately:
        sub.status = Subscription.Status.CANCELED
        sub.canceled_at = timezone.now()
    else:
        sub.cancel_at_period_end = True
    sub.save()
    audit.record("billing.subscription_canceled", actor=actor, target=sub, after={"immediately": immediately})
    return sub


def resume_subscription(sub: Subscription, *, actor: Any) -> Subscription:
    if not sub.cancel_at_period_end or not sub.is_live:
        raise Conflict("Nothing to resume.")
    provider = get_provider(sub.provider)
    if hasattr(provider, "resume_subscription"):
        provider.resume_subscription(sub)
    sub.cancel_at_period_end = False
    sub.save(update_fields=["cancel_at_period_end", "updated_at"])
    return sub


def renew_due_subscriptions() -> int:
    """Charge Toss (and mock) subscriptions whose period ended. Stripe renews on its own."""
    now = timezone.now()
    count = 0
    due = Subscription.objects.filter(provider__in=["toss", "mock"], current_period_end__lte=now,
                                      status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE])
    for sub in due.select_related("plan", "user"):
        if sub.cancel_at_period_end:
            sub.status = Subscription.Status.EXPIRED
            sub.save(update_fields=["status", "updated_at"])
            continue
        start = sub.current_period_end or now
        payment = Payment.objects.create(
            user=sub.user, provider=sub.provider, kind=Payment.Kind.RENEWAL, order_id=new_order_id(),
            order_name=f"{localized(sub.plan.name, 'en')} — renewal"[:128], currency=sub.currency,
            amount=sub.plan.price_for(sub.currency), plan=sub.plan, subscription=sub,
            credits=sub.plan.monthly_credits, period_start=start, period_end=add_month(start),
        )
        try:
            if sub.provider == "toss":
                provider = get_provider("toss")
                verified = provider.charge_billing_key(
                    billing_key=sub.toss_billing_key, customer_key=provider._customer_key(sub.user),
                    order_id=payment.order_id, order_name=payment.order_name, amount=payment.amount,
                    email=sub.user.email)
            else:
                verified = VerifiedPayment(f"mock_{payment.order_id}", payment.amount, payment.currency, "mock")
            fulfil_payment(payment, verified)
            count += 1
        except Exception as exc:  # noqa: BLE001 - one failed renewal must not stop the batch
            logger.warning("Renewal failed for %s: %s", sub.pk, exc)
            payment.status = Payment.Status.FAILED
            payment.failure_reason = str(exc)[:255]
            payment.save(update_fields=["status", "failure_reason", "updated_at"])
            sub.failed_attempts += 1
            sub.status = Subscription.Status.PAST_DUE if sub.failed_attempts < 3 else Subscription.Status.EXPIRED
            sub.save(update_fields=["failed_attempts", "status", "updated_at"])
    return count


# --- refunds -----------------------------------------------------------------------------

@dataclass
class RefundQuote:
    eligible: bool
    amount: int
    credits_to_revoke: int
    reason: str


def refund_quote(payment: Payment, *, override_full: bool = False) -> RefundQuote:
    refundable = payment.amount - payment.refunded_amount
    buckets = list(CreditBucket.objects.filter(payment=payment))
    paid = [b for b in buckets if b.source in (CreditSource.PURCHASE, CreditSource.SUBSCRIPTION)]
    remaining_paid = sum(b.amount_remaining for b in paid)
    all_remaining = sum(b.amount_remaining for b in buckets)
    if payment.status not in (Payment.Status.PAID, Payment.Status.PARTIALLY_REFUNDED) or refundable <= 0:
        return RefundQuote(False, 0, 0, "Payment is not refundable.")
    if override_full:
        return RefundQuote(True, refundable, all_remaining, "Full refund (company fault).")
    now = timezone.now()
    paid_at = payment.paid_at or payment.created_at
    if payment.kind == Payment.Kind.PACK:
        if now - paid_at > PACK_REFUND_WINDOW:
            return RefundQuote(False, 0, 0, "The 30-day refund window has passed.")
        purchased = sum(b.amount_initial for b in paid) or 1
        amount = min(refundable, payment.amount * remaining_paid // purchased)
        return RefundQuote(amount > 0, amount, all_remaining,
                           f"{remaining_paid}/{purchased} paid credits unused (bonus credits are not refunded).")
    # subscription / renewal
    start = payment.period_start or paid_at
    end = payment.period_end or add_month(start)
    used = sum(b.amount_initial - b.amount_remaining for b in paid)
    if now - paid_at <= SUBSCRIPTION_WITHDRAWAL_WINDOW and used == 0:
        return RefundQuote(True, refundable, all_remaining, "Within 7 days and unused: full refund.")
    total_days = max(1, (end - start).days)
    days_left = max(0, (end - now).days)
    amount = min(refundable, payment.amount * days_left // total_days)
    return RefundQuote(amount > 0, amount, all_remaining, f"Pro-rata: {days_left}/{total_days} days remaining.")


def refund_payment(payment: Payment, *, actor: Any, reason: str, override_full: bool = False,
                   amount: int | None = None) -> Refund:
    quote = refund_quote(payment, override_full=override_full)
    if not quote.eligible:
        raise Conflict(quote.reason)
    amount = min(amount or quote.amount, quote.amount)
    refund = Refund.objects.create(payment=payment, amount=amount, reason=reason[:255], actor=actor)
    try:
        refund.provider_refund_id = get_provider(payment.provider).refund(payment, amount, reason)
    except ApiError as exc:
        refund.status = Refund.Status.FAILED
        refund.error = str(exc.detail)[:255]
        refund.save()
        raise
    with transaction.atomic():
        revoked = 0
        for bucket in CreditBucket.objects.filter(payment=payment):
            revoked += credits.revoke_bucket(bucket, memo=f"Refund {payment.order_id}", actor=actor)
        refund.credits_revoked = revoked
        refund.status = Refund.Status.SUCCEEDED
        refund.save()
        payment.refunded_amount += amount
        payment.status = (Payment.Status.REFUNDED if payment.refunded_amount >= payment.amount
                          else Payment.Status.PARTIALLY_REFUNDED)
        payment.save(update_fields=["refunded_amount", "status", "updated_at"])
        if payment.subscription_id and payment.kind in (Payment.Kind.SUBSCRIPTION, Payment.Kind.RENEWAL):
            sub = payment.subscription
            if sub.is_live:
                try:
                    get_provider(sub.provider).cancel_subscription(sub, at_period_end=False)
                except ApiError:
                    logger.warning("Could not cancel subscription %s at provider", sub.pk)
                sub.status = Subscription.Status.CANCELED
                sub.canceled_at = timezone.now()
                sub.save()
    audit.record("billing.refund", actor=actor, target=payment,
                 after={"amount": amount, "credits_revoked": revoked, "reason": reason})
    return refund


def display_price(amount: int, currency: str) -> str:
    return f"₩{amount:,}" if currency == Currency.KRW else f"${amount / 100:,.2f}"
