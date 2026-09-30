"""Credit packs, subscription plans, payments, refunds and provider webhooks.

Money amounts are integers in the currency's minor unit: KRW has no minor unit
(₩15,000 → 15000); USD is in cents ($12.00 → 1200).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from sml.core.crypto import EncryptedTextField
from sml.core.models import TimeStampedModel


class Provider(models.TextChoices):
    TOSS = "toss", "Toss Payments"
    STRIPE = "stripe", "Stripe"
    MOCK = "mock", "Mock (development)"


class Currency(models.TextChoices):
    KRW = "KRW", "₩ KRW"
    USD = "USD", "$ USD"


def localized(value: dict | None, lang: str) -> str:
    value = value or {}
    return value.get(lang) or value.get("en") or next(iter(value.values()), "")


class CreditPack(TimeStampedModel):
    slug = models.SlugField(unique=True)
    name = models.JSONField(help_text='{"en": "...", "ko": "...", "de": "..."}')
    credits = models.PositiveIntegerField()
    bonus_credits = models.PositiveIntegerField(default=0, help_text="Non-refundable bonus on top of paid credits.")
    price_krw = models.PositiveIntegerField()
    price_usd_cents = models.PositiveIntegerField()
    credit_expiry_days = models.PositiveIntegerField(
        null=True, blank=True, help_text="Empty = platform default for purchased credits."
    )
    highlight = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "credits"]

    def __str__(self) -> str:
        return localized(self.name, "en")

    def price_for(self, currency: str) -> int:
        return self.price_krw if currency == Currency.KRW else self.price_usd_cents


class Plan(TimeStampedModel):
    class Priority(models.IntegerChoices):
        NORMAL = 0, "Normal"
        PRIORITY = 1, "Priority"
        HIGHEST = 2, "Highest"

    slug = models.SlugField(unique=True)
    name = models.JSONField()
    description = models.JSONField(default=dict, blank=True)
    features = models.JSONField(default=dict, blank=True, help_text='{"en": ["...", ...], "ko": [...]}')
    monthly_credits = models.PositiveIntegerField()
    price_krw = models.PositiveIntegerField()
    price_usd_cents = models.PositiveIntegerField()
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    retention_days = models.PositiveIntegerField(default=30)
    api_access = models.BooleanField(default=True)
    max_inflight_tasks = models.PositiveIntegerField(default=8)
    highlight = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price_usd_cents"]

    def __str__(self) -> str:
        return localized(self.name, "en")

    def price_for(self, currency: str) -> int:
        return self.price_krw if currency == Currency.KRW else self.price_usd_cents


class BillingCustomer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing")
    stripe_customer_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # Toss customerKey: an opaque random id (never the user's email or PK).
    toss_customer_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    provider = models.CharField(max_length=16, choices=Provider.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INCOMPLETE, db_index=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    provider_subscription_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    toss_billing_key = EncryptedTextField(blank=True, default="")
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.plan.slug}:{self.status}"

    @property
    def is_live(self) -> bool:
        return self.status in (self.Status.ACTIVE, self.Status.PAST_DUE)


class Payment(TimeStampedModel):
    class Kind(models.TextChoices):
        PACK = "pack", "Credit pack"
        SUBSCRIPTION = "subscription", "Subscription (first payment)"
        RENEWAL = "renewal", "Subscription renewal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=16, choices=Provider.choices)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    order_id = models.CharField(max_length=64, unique=True)
    order_name = models.CharField(max_length=128)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    amount = models.PositiveIntegerField(help_text="Minor units (KRW: won, USD: cents).")
    pack = models.ForeignKey(CreditPack, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="payments")
    credits = models.PositiveIntegerField(default=0)
    bonus_credits = models.PositiveIntegerField(default=0)
    provider_payment_id = models.CharField(max_length=200, blank=True, default="", db_index=True)
    provider_session_id = models.CharField(max_length=200, blank=True, default="", db_index=True)
    method = models.CharField(max_length=64, blank=True, default="")
    receipt_url = models.URLField(max_length=500, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    refunded_amount = models.PositiveIntegerField(default=0)
    provider_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_id} {self.amount} {self.currency} {self.status}"


class Refund(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.PositiveIntegerField()
    credits_revoked = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    provider_refund_id = models.CharField(max_length=200, blank=True, default="")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    error = models.CharField(max_length=255, blank=True, default="")


class WebhookEvent(models.Model):
    provider = models.CharField(max_length=16, choices=Provider.choices)
    event_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="uniq_webhook_event")]
