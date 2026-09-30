"""Credit ledger: balances, holds, expiry order and the ledger/bucket invariant."""

from __future__ import annotations

import contextlib
import random
from datetime import timedelta

import pytest
import time_machine
from django.utils import timezone

from sml.core.exceptions import InsufficientCredits
from sml.credits import services as credits
from sml.credits.models import CreditBucket, CreditHold, CreditSource, LedgerEntry, LedgerKind

pytestmark = pytest.mark.django_db


def wallet_ok(user) -> bool:  # type: ignore[no-untyped-def]
    return credits.verify_wallet(credits.ensure_wallet(user))


def give(user, amount: int, *, days: int | None = None, source: str = CreditSource.PURCHASE):  # type: ignore[no-untyped-def]
    expires = timezone.now() + timedelta(days=days) if days is not None else None
    return credits.grant(user, amount, source=source, kind=LedgerKind.PURCHASE, expires_at=expires)


def test_new_user_has_wallet_and_zero_balance(user):
    assert credits.get_balance(user).balance == 0
    assert wallet_ok(user)


def test_grant_reserve_capture(user):
    give(user, 20)
    hold = credits.reserve(user, 7, reference_type="job", reference_id="j1")
    assert credits.get_balance(user).balance == 13
    assert credits.get_balance(user).held == 7
    credits.capture(hold)
    summary = credits.get_balance(user)
    assert summary.balance == 13 and summary.held == 0
    assert wallet_ok(user)


def test_release_returns_credits_to_their_buckets(user):
    a = give(user, 3, days=1)
    b = give(user, 10)
    hold = credits.reserve(user, 5, reference_type="job", reference_id="j1")
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.amount_remaining, b.amount_remaining) == (0, 8)
    credits.release(hold)
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.amount_remaining, b.amount_remaining) == (3, 10)
    assert wallet_ok(user)


def test_capture_and_release_are_idempotent(user):
    give(user, 10)
    hold = credits.reserve(user, 4, reference_type="job", reference_id="j1")
    credits.capture(hold)
    credits.capture(hold)
    credits.release(hold)  # already captured: no effect
    assert credits.get_balance(user).balance == 6
    assert wallet_ok(user)


def test_reserve_is_idempotent_per_reference(user):
    give(user, 10)
    h1 = credits.reserve(user, 4, reference_type="job", reference_id="same")
    h2 = credits.reserve(user, 4, reference_type="job", reference_id="same")
    assert h1.pk == h2.pk
    assert credits.get_balance(user).balance == 6


def test_insufficient_credits_raises_and_changes_nothing(user):
    give(user, 2)
    with pytest.raises(InsufficientCredits) as exc:
        credits.reserve(user, 3, reference_type="job", reference_id="j1")
    assert exc.value.extra == {"required": 3, "balance": 2}
    assert credits.get_balance(user).balance == 2
    assert not CreditHold.objects.exists()
    assert wallet_ok(user)


def test_soonest_expiring_credits_are_spent_first(user):
    never = give(user, 10)
    later = give(user, 10, days=30)
    soon = give(user, 3, days=1)
    credits.reserve(user, 5, reference_type="job", reference_id="j1")
    for b in (never, later, soon):
        b.refresh_from_db()
    assert soon.amount_remaining == 0
    assert later.amount_remaining == 8
    assert never.amount_remaining == 10


def test_expired_credits_leave_the_balance_with_a_ledger_entry(user):
    give(user, 5, days=1)
    give(user, 2)
    with time_machine.travel(timezone.now() + timedelta(days=2)):
        assert credits.get_balance(user).balance == 2
    assert LedgerEntry.objects.filter(kind=LedgerKind.EXPIRE, delta=-5).count() == 1
    assert wallet_ok(user)


def test_released_credits_expire_if_their_bucket_expired_meanwhile(user):
    give(user, 5, days=1)
    hold = credits.reserve(user, 5, reference_type="job", reference_id="j1")
    with time_machine.travel(timezone.now() + timedelta(days=2)):
        credits.release(hold)
        assert credits.get_balance(user).balance == 0
    assert wallet_ok(user)


def test_daily_free_credits_granted_once_per_day_without_carry_over(user, platform):
    platform.daily_free_credits = 10
    platform.save()
    start = timezone.now().replace(hour=3)  # 12:00 KST
    with time_machine.travel(start, tick=False):
        assert credits.get_balance(user).balance == 10
        assert credits.get_balance(user).balance == 10  # not granted twice
        credits.reserve(user, 4, reference_type="job", reference_id="j1")
    with time_machine.travel(start + timedelta(days=1), tick=False):
        # Yesterday's 6 unused expired at midnight KST; today's 10 are fresh.
        assert credits.get_balance(user).balance == 10
    assert CreditBucket.objects.filter(source=CreditSource.DAILY_FREE).count() == 2
    assert wallet_ok(user)


def test_signup_bonus_is_granted_only_once(user, platform):
    platform.signup_bonus_credits = 50
    platform.save()
    credits.grant_signup_bonus(user)
    credits.grant_signup_bonus(user)
    assert credits.get_balance(user).balance == 50


def test_unlimited_policy_reserves_nothing(user):
    user.access_policy.unlimited_credits = True
    user.access_policy.save()
    hold = credits.reserve(user, 999, reference_type="job", reference_id="j1")
    assert hold.unlimited and hold.amount == 0
    assert wallet_ok(user)


def test_admin_deduction_never_goes_negative(user, make_user):
    admin = make_user(roles=("admin",))
    give(user, 3)
    entry = credits.admin_adjust(user, -10, actor=admin, reason="chargeback")
    assert entry.delta == -3
    assert credits.get_balance(user).balance == 0
    assert wallet_ok(user)


def test_revoke_bucket_removes_only_what_is_left(user):
    bucket = give(user, 10)
    credits.capture(credits.reserve(user, 4, reference_type="job", reference_id="j1"))
    assert credits.revoke_bucket(bucket, memo="refund") == 6
    assert credits.get_balance(user).balance == 0
    assert wallet_ok(user)


@pytest.mark.parametrize("seed", range(6))
def test_random_operation_sequences_keep_the_ledger_consistent(user, seed):
    """Property check: any sequence of operations keeps sum(ledger) == sum(buckets) and balance >= 0."""
    rng = random.Random(seed)
    holds: list[CreditHold] = []
    for step in range(60):
        op = rng.choice(["grant", "grant_exp", "reserve", "capture", "release", "adjust"])
        if op == "grant":
            give(user, rng.randint(1, 20))
        elif op == "grant_exp":
            give(user, rng.randint(1, 20), days=rng.randint(1, 3))
        elif op == "reserve":
            with contextlib.suppress(InsufficientCredits):
                holds.append(credits.reserve(user, rng.randint(0, 15), reference_type="job",
                                             reference_id=f"{seed}-{step}"))
        elif op in ("capture", "release") and holds:
            hold = holds.pop(rng.randrange(len(holds)))
            (credits.capture if op == "capture" else credits.release)(hold)
        elif op == "adjust":
            credits.admin_adjust(user, rng.choice([-1, 1]) * rng.randint(1, 10), actor=None, reason="test")
        summary = credits.get_balance(user)
        assert summary.balance >= 0
        assert wallet_ok(user), f"invariant broken after step {step} ({op})"
