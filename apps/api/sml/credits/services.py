"""Credit ledger operations. The only code allowed to change credit balances.

Every public function takes the wallet row lock, applies its change to buckets
and writes matching ledger entries in the same transaction. Consumption order is
"soonest-expiring first": daily free → signup bonus → subscription → purchased
→ non-expiring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from sml.core.events import publish_to_user
from sml.core.exceptions import InsufficientCredits
from sml.core.models import PlatformSettings

from .models import CreditBucket, CreditHold, CreditSource, CreditWallet, LedgerEntry, LedgerKind

logger = logging.getLogger(__name__)


# --- helpers -------------------------------------------------------------------

def business_tz() -> ZoneInfo:
    return ZoneInfo(settings.BUSINESS_TIME_ZONE)


def business_today() -> Any:
    return timezone.localdate(timezone=business_tz())


def next_business_midnight(now: datetime | None = None) -> datetime:
    local = (now or timezone.now()).astimezone(business_tz())
    tomorrow = local.date() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=business_tz())


def ensure_wallet(user: Any) -> CreditWallet:
    wallet, _ = CreditWallet.objects.get_or_create(user=user)
    return wallet


def _locked_wallet(user: Any) -> CreditWallet:
    ensure_wallet(user)
    return CreditWallet.objects.select_for_update().get(user=user)


def _live_buckets(wallet: CreditWallet, now: datetime) -> Any:
    return wallet.buckets.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now), amount_remaining__gt=0)


def _available(wallet: CreditWallet, now: datetime) -> int:
    return _live_buckets(wallet, now).aggregate(total=Sum("amount_remaining"))["total"] or 0


def _ledger_sum(wallet: CreditWallet) -> int:
    return wallet.ledger.aggregate(total=Sum("delta"))["total"] or 0


def _write(
    wallet: CreditWallet,
    kind: str,
    delta: int,
    now: datetime,
    *,
    bucket: CreditBucket | None = None,
    hold: CreditHold | None = None,
    reference_type: str = "",
    reference_id: str = "",
    actor: Any = None,
    memo: str = "",
    idempotency_key: str | None = None,
) -> LedgerEntry:
    entry = LedgerEntry.objects.create(
        wallet=wallet,
        kind=kind,
        delta=delta,
        balance_after=_available(wallet, now),
        bucket=bucket,
        hold=hold,
        reference_type=reference_type,
        reference_id=reference_id,
        actor=actor,
        memo=memo[:255],
        idempotency_key=idempotency_key,
    )
    return entry


def _refresh_cache(wallet: CreditWallet, now: datetime) -> int:
    balance = _available(wallet, now)
    if wallet.balance_cache != balance:
        CreditWallet.objects.filter(pk=wallet.pk).update(balance_cache=balance)
        wallet.balance_cache = balance
    return balance


def _notify(wallet: CreditWallet, balance: int) -> None:
    user_id = wallet.user_id
    transaction.on_commit(lambda: publish_to_user(user_id, "credits.updated", {"balance": balance}))


def _expire_due(wallet: CreditWallet, now: datetime) -> None:
    due = wallet.buckets.filter(expires_at__lte=now, amount_remaining__gt=0)
    for bucket in due:
        amount = bucket.amount_remaining
        bucket.amount_remaining = 0
        bucket.save(update_fields=["amount_remaining", "updated_at"])
        _write(wallet, LedgerKind.EXPIRE, -amount, now, bucket=bucket,
               memo=f"{bucket.get_source_display()} expired")


def _daily_grant(wallet: CreditWallet, now: datetime) -> None:
    amount = PlatformSettings.load().daily_free_credits
    if amount <= 0:
        return
    today = business_today()
    if wallet.buckets.filter(source=CreditSource.DAILY_FREE, grant_date=today).exists():
        return
    try:
        with transaction.atomic():
            bucket = CreditBucket.objects.create(
                wallet=wallet, source=CreditSource.DAILY_FREE, amount_initial=amount, amount_remaining=amount,
                expires_at=next_business_midnight(now), grant_date=today, memo="Daily free credits",
            )
    except IntegrityError:
        return
    _write(wallet, LedgerKind.DAILY_GRANT, amount, now, bucket=bucket, memo=f"Daily free credits ({today})")


def _housekeeping(wallet: CreditWallet, now: datetime, *, daily: bool = True) -> None:
    _expire_due(wallet, now)
    if daily and wallet.user.is_active:
        _daily_grant(wallet, now)


# --- read ----------------------------------------------------------------------

@dataclass(frozen=True)
class BalanceSummary:
    balance: int
    by_source: dict[str, int]
    next_expiry_at: datetime | None
    next_expiry_amount: int
    held: int
    unlimited: bool


def get_balance(user: Any) -> BalanceSummary:
    """Balance with lazy housekeeping (expiry + today's free grant)."""
    now = timezone.now()
    with transaction.atomic():
        wallet = _locked_wallet(user)
        _housekeeping(wallet, now)
        balance = _refresh_cache(wallet, now)
        live = list(_live_buckets(wallet, now).order_by(F("expires_at").asc(nulls_last=True)))
        held = wallet.holds.filter(status=CreditHold.Status.HELD).aggregate(t=Sum("amount"))["t"] or 0
    by_source: dict[str, int] = {}
    for b in live:
        by_source[b.source] = by_source.get(b.source, 0) + b.amount_remaining
    expiring = [b for b in live if b.expires_at is not None]
    next_at = expiring[0].expires_at if expiring else None
    next_amount = sum(b.amount_remaining for b in expiring if b.expires_at == next_at) if next_at else 0
    policy = getattr(user, "access_policy", None)
    return BalanceSummary(balance, by_source, next_at, next_amount, held,
                          bool(policy and policy.unlimited_credits))


# --- grants --------------------------------------------------------------------

def grant(
    user: Any,
    amount: int,
    *,
    source: str,
    kind: str,
    expires_at: datetime | None = None,
    payment: Any = None,
    subscription: Any = None,
    actor: Any = None,
    memo: str = "",
    idempotency_key: str | None = None,
) -> CreditBucket | None:
    """Add credits in a new bucket. Idempotent when `idempotency_key` is given."""
    if amount <= 0:
        raise ValueError("Grant amount must be positive")
    now = timezone.now()
    with transaction.atomic():
        wallet = _locked_wallet(user)
        if idempotency_key and LedgerEntry.objects.filter(idempotency_key=idempotency_key).exists():
            return None
        bucket = CreditBucket.objects.create(
            wallet=wallet, source=source, amount_initial=amount, amount_remaining=amount,
            expires_at=expires_at, payment=payment, subscription=subscription, memo=memo[:255],
        )
        _write(wallet, kind, amount, now, bucket=bucket, actor=actor, memo=memo,
               reference_type="payment" if payment else "", reference_id=str(payment.pk) if payment else "",
               idempotency_key=idempotency_key)
        balance = _refresh_cache(wallet, now)
    _notify(wallet, balance)
    return bucket


def grant_signup_bonus(user: Any) -> CreditBucket | None:
    cfg = PlatformSettings.load()
    if cfg.signup_bonus_credits <= 0:
        return None
    expires = timezone.now() + timedelta(days=cfg.signup_bonus_expiry_days) if cfg.signup_bonus_expiry_days else None
    return grant(user, cfg.signup_bonus_credits, source=CreditSource.SIGNUP_BONUS, kind=LedgerKind.SIGNUP_BONUS,
                 expires_at=expires, memo="Welcome bonus", idempotency_key=f"signup-bonus:{user.pk}")


# --- reservation lifecycle -------------------------------------------------------

def reserve(user: Any, amount: int, *, reference_type: str, reference_id: str) -> CreditHold:
    """Move `amount` credits from buckets into a hold. Raises InsufficientCredits."""
    if amount < 0:
        raise ValueError("Amount must be >= 0")
    now = timezone.now()
    policy = getattr(user, "access_policy", None)
    with transaction.atomic():
        wallet = _locked_wallet(user)
        existing = wallet.holds.filter(reference_type=reference_type, reference_id=reference_id).first()
        if existing is not None:
            return existing
        if policy is not None and policy.unlimited_credits:
            return CreditHold.objects.create(wallet=wallet, amount=0, unlimited=True,
                                             reference_type=reference_type, reference_id=reference_id)
        _housekeeping(wallet, now)
        available = _available(wallet, now)
        if available < amount:
            raise InsufficientCredits(
                f"This request costs {amount} credits but your balance is {available}.",
                extra={"required": amount, "balance": available},
            )
        hold = CreditHold.objects.create(wallet=wallet, amount=amount, reference_type=reference_type,
                                         reference_id=reference_id)
        remaining = amount
        allocations: list[dict[str, Any]] = []
        buckets = (_live_buckets(wallet, now).select_for_update()
                   .order_by(F("expires_at").asc(nulls_last=True), "created_at"))
        for bucket in buckets:
            if remaining == 0:
                break
            take = min(bucket.amount_remaining, remaining)
            CreditBucket.objects.filter(pk=bucket.pk).update(amount_remaining=F("amount_remaining") - take)
            allocations.append({"bucket": str(bucket.pk), "amount": take})
            remaining -= take
        hold.allocations = allocations
        hold.save(update_fields=["allocations"])
        if amount:
            _write(wallet, LedgerKind.RESERVE, -amount, now, hold=hold, reference_type=reference_type,
                   reference_id=reference_id, memo=f"Reserved for {reference_type}")
        balance = _refresh_cache(wallet, now)
    _notify(wallet, balance)
    return hold


def capture(hold: CreditHold, *, memo: str = "") -> CreditHold:
    """Finalize a hold: the reserved credits are spent."""
    now = timezone.now()
    with transaction.atomic():
        wallet = CreditWallet.objects.select_for_update().get(pk=hold.wallet_id)
        hold = CreditHold.objects.select_for_update().get(pk=hold.pk)
        if hold.status != CreditHold.Status.HELD:
            return hold
        hold.status = CreditHold.Status.CAPTURED
        hold.settled_at = now
        hold.save(update_fields=["status", "settled_at", "updated_at"])
        if hold.amount:
            _write(wallet, LedgerKind.CAPTURE, 0, now, hold=hold, reference_type=hold.reference_type,
                   reference_id=hold.reference_id, memo=memo or f"Charged {hold.amount} credits")
    return hold


def release(hold: CreditHold, *, memo: str = "") -> CreditHold:
    """Cancel a hold and return every credit to the bucket it came from."""
    now = timezone.now()
    with transaction.atomic():
        wallet = CreditWallet.objects.select_for_update().get(pk=hold.wallet_id)
        hold = CreditHold.objects.select_for_update().get(pk=hold.pk)
        if hold.status != CreditHold.Status.HELD:
            return hold
        for alloc in hold.allocations:
            CreditBucket.objects.filter(pk=alloc["bucket"]).update(
                amount_remaining=F("amount_remaining") + int(alloc["amount"])
            )
        hold.status = CreditHold.Status.RELEASED
        hold.settled_at = now
        hold.save(update_fields=["status", "settled_at", "updated_at"])
        if hold.amount:
            _write(wallet, LedgerKind.RELEASE, hold.amount, now, hold=hold, reference_type=hold.reference_type,
                   reference_id=hold.reference_id, memo=memo or "Refunded (not charged)")
        # Credits returned to an already-expired bucket expire immediately.
        _expire_due(wallet, now)
        balance = _refresh_cache(wallet, now)
    _notify(wallet, balance)
    return hold


# --- admin / billing adjustments --------------------------------------------------

def admin_adjust(user: Any, delta: int, *, actor: Any, reason: str,
                 expires_at: datetime | None = None) -> LedgerEntry:
    if delta == 0:
        raise ValueError("delta must be non-zero")
    if delta > 0:
        grant(user, delta, source=CreditSource.ADMIN_GRANT, kind=LedgerKind.ADMIN_GRANT,
              expires_at=expires_at, actor=actor, memo=reason)
        return LedgerEntry.objects.filter(wallet__user=user, kind=LedgerKind.ADMIN_GRANT).latest("created_at")
    amount = -delta
    now = timezone.now()
    with transaction.atomic():
        wallet = _locked_wallet(user)
        _expire_due(wallet, now)
        available = _available(wallet, now)
        take_total = min(amount, available)
        remaining = take_total
        for bucket in (_live_buckets(wallet, now).select_for_update()
                       .order_by(F("expires_at").asc(nulls_last=True), "created_at")):
            if remaining == 0:
                break
            take = min(bucket.amount_remaining, remaining)
            CreditBucket.objects.filter(pk=bucket.pk).update(amount_remaining=F("amount_remaining") - take)
            remaining -= take
        entry = _write(wallet, LedgerKind.ADMIN_DEDUCT, -take_total, now, actor=actor, memo=reason)
        balance = _refresh_cache(wallet, now)
    _notify(wallet, balance)
    return entry


def revoke_bucket(bucket: CreditBucket, *, kind: str = LedgerKind.REFUND, memo: str = "",
                  actor: Any = None) -> int:
    """Remove whatever is left in a bucket (e.g. after a purchase is refunded). Returns credits removed."""
    now = timezone.now()
    with transaction.atomic():
        wallet = CreditWallet.objects.select_for_update().get(pk=bucket.wallet_id)
        bucket = CreditBucket.objects.select_for_update().get(pk=bucket.pk)
        amount = bucket.amount_remaining
        if amount == 0:
            return 0
        bucket.amount_remaining = 0
        bucket.save(update_fields=["amount_remaining", "updated_at"])
        _write(wallet, kind, -amount, now, bucket=bucket, actor=actor, memo=memo,
               reference_type="payment" if bucket.payment_id else "",
               reference_id=str(bucket.payment_id or ""))
        balance = _refresh_cache(wallet, now)
    _notify(wallet, balance)
    return amount


def expire_all_due() -> int:
    """Periodic sweep so expirations show in the ledger even for idle users."""
    now = timezone.now()
    wallet_ids = (CreditBucket.objects.filter(expires_at__lte=now, amount_remaining__gt=0)
                  .values_list("wallet_id", flat=True).distinct())
    count = 0
    for wallet_id in wallet_ids:
        with transaction.atomic():
            wallet = CreditWallet.objects.select_for_update().get(pk=wallet_id)
            _expire_due(wallet, now)
            _refresh_cache(wallet, now)
            count += 1
    return count


def release_stale_holds(max_age: timedelta = timedelta(hours=24)) -> int:
    """Nightly reconciliation: release holds whose job is finished but were never settled."""
    from sml.jobs.models import Job

    cutoff = timezone.now() - max_age
    released = 0
    for hold in CreditHold.objects.filter(status=CreditHold.Status.HELD, created_at__lt=cutoff):
        if hold.reference_type == "job":
            job = Job.objects.filter(pk=hold.reference_id).first()
            if job is not None and not job.is_terminal:
                continue
        logger.warning("Releasing stale hold %s (%s:%s)", hold.pk, hold.reference_type, hold.reference_id)
        release(hold, memo="Released by reconciliation")
        released += 1
    return released


def verify_wallet(wallet: CreditWallet) -> bool:
    """Ledger/bucket consistency check used by tests and the reconciliation task."""
    remaining = wallet.buckets.aggregate(t=Sum("amount_remaining"))["t"] or 0
    return _ledger_sum(wallet) == remaining


def audit_ledgers() -> list[str]:
    """Nightly check of the ledger invariant for every wallet. Returns the inconsistent wallet ids.

    Both totals are read in one repeatable-read snapshot; suspects are re-checked under the
    wallet lock so a reservation in flight is never reported as corruption.
    """
    from django.db import connection

    from sml.core import audit

    outermost = not connection.in_atomic_block
    with transaction.atomic():
        if connection.vendor == "postgresql" and outermost:
            with connection.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        ledger = dict(LedgerEntry.objects.values("wallet_id").annotate(t=Sum("delta")).values_list("wallet_id", "t"))
        buckets = dict(CreditBucket.objects.values("wallet_id").annotate(t=Sum("amount_remaining"))
                       .values_list("wallet_id", "t"))
    suspects = [w for w in set(ledger) | set(buckets) if (ledger.get(w) or 0) != (buckets.get(w) or 0)]
    confirmed: list[str] = []
    for wallet_id in suspects:
        with transaction.atomic():
            wallet = CreditWallet.objects.select_for_update().get(pk=wallet_id)
            if not verify_wallet(wallet):
                confirmed.append(str(wallet_id))
                logger.error("Credit ledger mismatch for wallet %s (user %s)", wallet_id, wallet.user_id)
    if confirmed:
        audit.record("credits.ledger_mismatch", target_type="credits.creditwallet",
                     after={"count": len(confirmed), "wallets": confirmed[:100]})
    return confirmed

