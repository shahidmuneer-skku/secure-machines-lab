"""Cross-cutting security: authentication, object ownership (IDOR), RBAC + MFA, headers, errors."""

from __future__ import annotations

import uuid

import pytest

from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind
from sml.jobs import services as job_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def owned_job(user, make_media):  # type: ignore[no-untyped-def]
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    return job_services.create_job(user, job_services.JobRequest(media=make_media(user)))


# --- authentication -----------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/v1/me", "/api/v1/jobs", "/api/v1/credits/balance", "/api/v1/api-keys"])
def test_private_endpoints_need_authentication(client_for, path):
    res = client_for().get(path)
    assert res.status_code in (401, 403)
    assert res["Content-Type"].startswith("application/problem+json")
    assert {"type", "title", "status", "code"} <= set(res.json())


def test_public_endpoints_are_open(client_for, db):
    client = client_for()
    for path in ("/api/healthz", "/api/v1/config", "/api/v1/billing/catalog", "/api/v1/trial/status"):
        assert client.get(path).status_code == 200, path


# --- ownership --------------------------------------------------------------------------

def test_users_cannot_reach_each_others_jobs_or_media(client_for, owned_job, make_user):
    intruder = client_for(make_user())
    job_id, media_id = owned_job.pk, owned_job.media_id
    for method, path in [
        ("get", f"/api/v1/jobs/{job_id}"),
        ("post", f"/api/v1/jobs/{job_id}/cancel"),
        ("post", f"/api/v1/jobs/{job_id}/rerun"),
        ("delete", f"/api/v1/jobs/{job_id}"),
        ("get", f"/api/v1/media/{media_id}"),
        ("get", f"/api/v1/media/{media_id}/content"),
        ("get", f"/api/v1/media/{media_id}/thumbnail"),
        ("post", f"/api/v1/jobs/{job_id}/reports"),
    ]:
        res = getattr(intruder, method)(path, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        assert res.status_code == 404, f"{method.upper()} {path} → {res.status_code}"
    assert job_id not in [j["id"] for j in intruder.get("/api/v1/jobs").json()["results"]]


def test_jobs_cannot_be_created_from_someone_elses_media(client_for, owned_job, make_user):
    intruder = make_user()
    credits.grant(intruder, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    res = client_for(intruder).post("/api/v1/jobs", {"media_id": str(owned_job.media_id)}, format="json",
                                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert res.status_code == 400
    assert res.json()["media_ids"] == [str(owned_job.media_id)]


def test_owner_sees_own_job(api, owned_job):
    res = api.get(f"/api/v1/jobs/{owned_job.pk}")
    assert res.status_code == 200
    assert res.json()["status"] == "queued"


# --- roles and MFA ------------------------------------------------------------------------

def test_regular_users_cannot_use_admin_endpoints(api):
    assert api.get("/api/v1/admin/overview").status_code == 403
    assert api.get("/api/v1/admin/users").status_code == 403


def test_staff_need_an_mfa_verified_session(client_for, make_user):
    admin = make_user(roles=("admin",))
    res = client_for(admin).get("/api/v1/admin/overview")
    assert res.status_code == 403 and res.json()["code"] == "MFA_REQUIRED"
    assert client_for(admin, mfa=True).get("/api/v1/admin/overview").status_code == 200


def test_capabilities_limit_what_staff_can_do(client_for, make_user, user):
    support = client_for(make_user(roles=("support",)), mfa=True)
    assert support.get("/api/v1/admin/users").status_code == 200
    res = support.post(f"/api/v1/admin/users/{user.pk}/credits", {"delta": 100, "reason": "x"}, format="json")
    assert res.status_code == 403
    assert support.get("/api/v1/admin/settings").status_code == 200  # staff may read settings
    assert support.patch("/api/v1/admin/settings", {"daily_free_credits": 99}, format="json").status_code == 403
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    res = admin.post(f"/api/v1/admin/users/{user.pk}/credits", {"delta": 100, "reason": "goodwill"}, format="json")
    assert res.status_code == 200, res.content
    assert res.json()["balance"] == 100
    assert admin.patch("/api/v1/admin/settings", {"daily_free_credits": 99}, format="json").status_code == 403


def test_disabled_accounts_lose_access(client_for, make_user):
    target = make_user()
    client = client_for(target)
    assert client.get("/api/v1/me").status_code == 200
    target.is_active = False
    target.save()
    assert client.get("/api/v1/me").status_code in (401, 403)


# --- platform middleware ------------------------------------------------------------------

def test_security_headers_and_request_id(client_for, db):
    res = client_for().get("/api/healthz")
    assert res["X-Content-Type-Options"] == "nosniff"
    assert res["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in res
    assert res["X-Request-ID"]


def test_maintenance_mode_blocks_writes_but_not_reads(api, platform):
    platform.maintenance_mode = True
    platform.save()
    assert api.get("/api/v1/me").status_code == 200
    res = api.post("/api/v1/api-keys", {"name": "x", "scopes": ["jobs:read"]}, format="json")
    assert res.status_code == 503
    assert res["Retry-After"] == "300"
    assert res.json()["code"] == "MAINTENANCE"


def test_validation_errors_use_problem_details(api):
    res = api.post("/api/v1/api-keys", {"scopes": ["not-a-scope"]}, format="json")
    assert res.status_code == 400
    body = res.json()
    assert body["status"] == 400 and body["code"]
    assert res["Content-Type"].startswith("application/problem+json")
