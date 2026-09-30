"""Credit wallet, expiring buckets, append-only ledger and reservation holds.

Invariants (covered by property tests):
  * sum(LedgerEntry.delta) == sum(CreditBucket.amount_remaining) for a wallet
  * CreditBucket.amount_remaining is never negative
  * every mutation happens under a row lock on the wallet (SELECT ... FOR UPDATE)
Balance shown to users = remaining credits in non-expired buckets.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from sml.core.models import TimeStampedModel, UUIDModel


class CreditWallet(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    # Denormalized cache for listings; authoritative value is computed from buckets.
    balance_cache = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"wallet:{self.user_id}"


class CreditSource(models.TextChoices):
    SIGNUP_BONUS = "signup_bonus", "Signup bonus"
    DAILY_FREE = "daily_free", "Daily free credits"
    PURCHASE = "purchase", "Purchased"
    SUBSCRIPTION = "subscription", "Subscription"
    PROMO = "promo", "Promotion"
    ADMIN_GRANT = "admin_grant", "Granted by admin"


class CreditBucket(TimeStampedModel):
    wallet = models.ForeignKey(CreditWallet, on_delete=models.CASCADE, related_name="buckets")
    source = models.CharField(max_length=32, choices=CreditSource.choices)
    amount_initial = models.PositiveIntegerField()
    amount_remaining = models.PositiveIntegerField()
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    grant_date = models.DateField(null=True, blank=True, help_text="Business date for daily grants.")
    payment = models.ForeignKey("billing.Payment", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="credit_buckets")
    subscription = models.ForeignKey("billing.Subscription", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="credit_buckets")
    memo = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "grant_date"], condition=Q(source="daily_free"), name="uniq_daily_grant"
            ),
            models.CheckConstraint(condition=Q(amount_remaining__lte=models.F("amount_initial")),
                                   name="bucket_remaining_lte_initial"),
        ]

    @property
    def is_paid(self) -> bool:
        return self.source in (CreditSource.PURCHASE, CreditSource.SUBSCRIPTION)


class LedgerKind(models.TextChoices):
    SIGNUP_BONUS = "signup_bonus", "Signup bonus"
    DAILY_GRANT = "daily_grant", "Daily free credits"
    PURCHASE = "purchase", "Purchase"
    SUBSCRIPTION_GRANT = "subscription_grant", "Subscription credits"
    PROMO = "promo", "Promotion"
    ADMIN_GRANT = "admin_grant", "Admin grant"
    ADMIN_DEDUCT = "admin_deduct", "Admin deduction"
    RESERVE = "reserve", "Reserved"
    CAPTURE = "capture", "Charged"
    RELEASE = "release", "Released"
    REFUND = "refund", "Refunded purchase"
    EXPIRE = "expire", "Expired"


class LedgerEntry(UUIDModel):
    wallet = models.ForeignKey(CreditWallet, on_delete=models.CASCADE, related_name="ledger")
    kind = models.CharField(max_length=32, choices=LedgerKind.choices, db_index=True)
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    bucket = models.ForeignKey(CreditBucket, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    hold = models.ForeignKey("CreditHold", null=True, blank=True, on_delete=models.SET_NULL, related_name="entries")
    reference_type = models.CharField(max_length=32, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    memo = models.CharField(max_length=255, blank=True, default="")
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["wallet", "-created_at"])]


class CreditHold(TimeStampedModel):
    class Status(models.TextChoices):
        HELD = "held", "Held"
        CAPTURED = "captured", "Captured"
        RELEASED = "released", "Released"

    wallet = models.ForeignKey(CreditWallet, on_delete=models.CASCADE, related_name="holds")
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.HELD, db_index=True)
    # [{"bucket": "<uuid>", "amount": 3}, ...] so releases return credits to their origin.
    allocations = models.JSONField(default=list)
    reference_type = models.CharField(max_length=32)
    reference_id = models.CharField(max_length=64, db_index=True)
    unlimited = models.BooleanField(default=False)
    settled_at = models.DateTimeField(null=True, blank=True)


class PriceRule(models.Model):
    """Admin-editable credit prices. Keys are fixed; values are credits."""

    class Key(models.TextChoices):
        IMAGE = "image", "Image (per file)"
        VIDEO_BASE = "video_base", "Video (per file, up to the base duration)"
        VIDEO_BASE_SECONDS = "video_base_seconds", "Video base duration (seconds)"
        VIDEO_PER_EXTRA_MINUTE = "video_per_extra_minute", "Video (per extra started minute)"
        LONG_VIDEO_PER_MINUTE = "long_video_per_minute", "Long-form video (per started minute)"
        NEWS_CASE = "news_case", "News verification (per case)"
        EXPLAIN = "explain", "Explain why (reasoning)"
        REPORT_PDF = "report_pdf", "PDF report"
        REPORT_HWP = "report_hwp", "HWP report"
        REPORT_CSV = "report_csv", "CSV report"

    key = models.CharField(max_length=40, choices=Key.choices, unique=True)
    credits = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    DEFAULTS = {
        Key.IMAGE: 1,
        Key.VIDEO_BASE: 10,
        Key.VIDEO_BASE_SECONDS: 60,
        Key.VIDEO_PER_EXTRA_MINUTE: 5,
        Key.LONG_VIDEO_PER_MINUTE: 4,
        Key.NEWS_CASE: 15,
        Key.EXPLAIN: 3,
        Key.REPORT_PDF: 0,
        Key.REPORT_HWP: 0,
        Key.REPORT_CSV: 0,
    }

    def __str__(self) -> str:
        return f"{self.key}={self.credits}"
