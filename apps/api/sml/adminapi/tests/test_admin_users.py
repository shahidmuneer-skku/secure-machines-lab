"""Admin user management: credit adjustments (including on one's own account), blocking, system page."""

from __future__ import annotations

import httpx
import pytest

from sml.adminapi import system
from sml.core.models import AuditLog


def credits(client, user, delta, reason="support"):  # type: ignore[no-untyped-def]
    return client.post(f"/api/v1/admin/users/{user.pk}/credits", {"delta": delta, "reason": reason}, format="json")


def test_admin_adds_and_removes_credits_on_their_own_account(client_for, make_user):
    me = make_user(roles=("admin",))
    admin = client_for(me, mfa=True)
    start = admin.get(f"/api/v1/admin/users/{me.pk}").json()["balance"]

    added = credits(admin, me, 50)
    assert added.status_code == 200, added.content
    assert added.json()["applied"] == 50 and added.json()["balance"] == start + 50

    removed = credits(admin, me, -20)
    assert removed.json()["applied"] == -20 and removed.json()["balance"] == start + 30

    ledger = admin.get(f"/api/v1/admin/users/{me.pk}/ledger").json()
    assert [e["delta"] for e in ledger[:2]] == [-20, 50]
    assert {e["actor__email"] for e in ledger[:2]} == {me.email}
    assert AuditLog.objects.filter(action="admin.credits_adjusted", actor=me).count() == 2


def test_removing_more_than_the_balance_takes_what_is_there(client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    target = make_user()
    credits(admin, target, 30)
    res = credits(admin, target, -100)
    assert res.json()["applied"] == -30 and res.json()["balance"] == 0
    empty = credits(admin, target, -1)
    assert empty.status_code == 409 and "no credits" in empty.json()["detail"]


def test_blocking_signs_the_user_out_and_is_audited(client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    target = make_user()
    session = client_for(target)
    assert session.get("/api/v1/me").status_code == 200

    res = admin.post(f"/api/v1/admin/users/{target.pk}/disable", {"reason": "Abuse report #12"}, format="json")
    assert res.status_code == 200, res.content
    assert res.json()["is_active"] is False and res.json()["disabled_reason"] == "Abuse report #12"
    assert session.get("/api/v1/me").status_code in (401, 403)
    assert AuditLog.objects.filter(action="admin.user_disabled", target_id=str(target.pk)).exists()

    assert admin.get("/api/v1/admin/users", {"is_active": "false"}).json()["results"][0]["id"] == str(target.pk)
    res = admin.post(f"/api/v1/admin/users/{target.pk}/enable")
    assert res.json()["is_active"] is True and res.json()["disabled_reason"] == ""


def test_block_reason_is_limited(client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    target = make_user()
    res = admin.post(f"/api/v1/admin/users/{target.pk}/disable", {"reason": "x" * 300}, format="json")
    assert res.status_code == 400
    target.refresh_from_db()
    assert target.is_active


def test_admins_cannot_block_themselves_or_a_super_admin(client_for, make_user):
    me = make_user(roles=("admin",))
    admin = client_for(me, mfa=True)
    assert admin.post(f"/api/v1/admin/users/{me.pk}/disable").status_code == 409
    boss = make_user(roles=("super_admin",))
    assert admin.post(f"/api/v1/admin/users/{boss.pk}/disable").status_code == 403
    other_boss = client_for(make_user(roles=("super_admin",)), mfa=True)
    assert other_boss.post(f"/api/v1/admin/users/{boss.pk}/disable").status_code == 200


@pytest.fixture
def services_down(monkeypatch):  # type: ignore[no-untyped-def]
    def refuse(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("connection refused to http://internal-host:8100")

    monkeypatch.setattr(system.httpx, "get", refuse)


def test_system_page_reports_services_without_leaking_errors(client_for, make_user, services_down):
    assert client_for(make_user(roles=("support",)), mfa=True).get("/api/v1/admin/system").status_code == 403
    res = client_for(make_user(roles=("admin",)), mfa=True).get("/api/v1/admin/system")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["checks"]["database"]["status"] == "ok"
    assert body["stream"]["status"] == "error" and body["agents"]["status"] == "error"
    assert body["configuration"]["toss"] in ("off", "test", "live")
    assert "internal-host" not in res.content.decode()


def test_gpus_are_grouped_per_card():
    stats = {"name": "RTX A5000", "util": 10, "mem_used_mb": 100, "mem_total_mb": 24000, "temp_c": 40}
    workers = [{"hostname": "h", "gpu": "0", "gpu_stats": stats}, {"hostname": "h", "gpu": "0", "gpu_stats": None},
               {"hostname": "h", "gpu": "", "queues": ["sml.news"]}]
    gpus = system._gpus(None, workers)
    assert len(gpus) == 1 and gpus[0]["workers"] == 2 and gpus[0]["stats"] == stats


@pytest.mark.parametrize(("secret", "mode"), [("", "off"), ("sk_test_1", "test"), ("sk_live_1", "live")])
def test_payment_modes(secret, mode):
    assert system._payment_mode(secret, ("sk_test_",)) == mode


def test_pinned_models_are_recognised():
    assert system._pinned("2319-01-10T12:14:27Z") and not system._pinned("2026-09-30T17:00:00Z")
