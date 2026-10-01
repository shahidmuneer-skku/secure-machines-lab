"""API keys: issuance, Bearer authentication, scopes, restrictions and ownership."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from sml.apikeys import services
from sml.apikeys.models import ApiKey, ApiKeyUsageDaily
from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind
from sml.jobs.models import Job

pytestmark = pytest.mark.django_db


class KeyClient(APIClient):
    """An API client that authenticates with a key and sends a fresh Idempotency-Key on every write."""

    def generic(self, method, path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            kwargs.setdefault("HTTP_IDEMPOTENCY_KEY", str(uuid.uuid4()))
        return super().generic(method, path, *args, **kwargs)


def bearer(raw: str) -> APIClient:
    client = KeyClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    return client


def issue(user, scopes=("detect:write", "jobs:read", "credits:read"), **kw):  # type: ignore[no-untyped-def]
    return services.issue_key(user, name="ci", scopes=list(scopes), **kw)


def test_create_returns_secret_once_and_stores_only_a_hash(api, user):
    res = api.post("/api/v1/api-keys", {"name": "Newsroom CMS", "scopes": ["detect:write", "jobs:read"]},
                   format="json")
    assert res.status_code == 201, res.content
    raw = res.json()["key"]
    assert services.KEY_RE.match(raw)
    key = ApiKey.objects.get(user=user)
    assert raw.split("_")[-1] not in (key.secret_hash, key.last_four)
    listed = api.get("/api/v1/api-keys").json()
    assert "key" not in listed[0]
    assert listed[0]["scopes"] == ["detect:write", "jobs:read"]


def test_valid_key_authenticates(user):
    res = bearer(issue(user).plaintext).get("/api/v1/credits/balance")
    assert res.status_code == 200
    assert ApiKey.objects.get(user=user).last_used_at is not None


@pytest.mark.parametrize("mutate", ["wrong_secret", "revoked", "expired", "owner_disabled"])
def test_invalid_keys_are_rejected(user, mutate):
    issued = issue(user)
    raw = issued.plaintext
    if mutate == "wrong_secret":
        raw = raw[:-4] + ("AAAA" if not raw.endswith("AAAA") else "BBBB")
    elif mutate == "revoked":
        services.revoke(issued.api_key)
    elif mutate == "expired":
        ApiKey.objects.filter(pk=issued.api_key.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    elif mutate == "owner_disabled":
        user.is_active = False
        user.save()
    res = bearer(raw).get("/api/v1/credits/balance")
    assert res.status_code == 401
    assert res["Content-Type"].startswith("application/problem+json")


def test_missing_scope_is_forbidden(user, png_upload):
    raw = issue(user, scopes=("jobs:read",)).plaintext
    res = bearer(raw).post("/api/v1/uploads", {"file": png_upload()}, format="multipart")
    assert res.status_code == 403


def test_ip_allowlist(user):
    raw = issue(user, allowed_ips=["10.0.0.0/8"]).plaintext
    assert bearer(raw).get("/api/v1/credits/balance", REMOTE_ADDR="127.0.0.1").status_code == 401
    assert bearer(raw).get("/api/v1/credits/balance", REMOTE_ADDR="10.1.2.3").status_code == 200


def test_keys_cannot_manage_keys_or_reach_admin(make_user):
    admin = make_user(roles=("super_admin",))
    raw = issue(admin).plaintext
    assert bearer(raw).get("/api/v1/api-keys").status_code == 403
    assert bearer(raw).post("/api/v1/api-keys", {"name": "x", "scopes": ["jobs:read"]}, format="json"
                            ).status_code == 403
    assert bearer(raw).get("/api/v1/admin/overview").status_code == 403


def test_rotate_revokes_the_old_key(api, user):
    old = issue(user)
    res = api.post(f"/api/v1/api-keys/{old.api_key.pk}/rotate")
    assert res.status_code == 201
    assert bearer(old.plaintext).get("/api/v1/credits/balance").status_code == 401
    assert bearer(res.json()["key"]).get("/api/v1/credits/balance").status_code == 200


def test_other_users_keys_are_invisible(client_for, user, make_user):
    key = issue(user).api_key
    other = client_for(make_user())
    assert other.get(f"/api/v1/api-keys/{key.pk}").status_code == 404
    assert other.delete(f"/api/v1/api-keys/{key.pk}").status_code == 404
    key.refresh_from_db()
    assert key.revoked_at is None


def test_one_call_detect_over_the_api(user, png_upload):
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    issued = issue(user)
    res = bearer(issued.plaintext).post("/api/v1/detect", {"file": png_upload()}, format="multipart")
    assert res.status_code == 202, res.content
    job = Job.objects.get(pk=res.json()["id"])
    assert job.source == Job.Source.API and job.api_key_id == issued.api_key.pk
    usage = ApiKeyUsageDaily.objects.get(api_key=issued.api_key)
    assert (usage.jobs_created, usage.credits_spent) == (1, 1)
    assert bearer(issued.plaintext).get(f"/api/v1/jobs/{job.pk}").status_code == 200


def test_api_callers_cannot_choose_or_see_detectors(user, make_media, use_detectors):
    import json

    from sml.catalog.registry import registry
    from sml.jobs.models import Job

    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    chosen, other = [m.id for m in registry().enabled_for("image")][:2]
    use_detectors([chosen])
    raw = issue(user).plaintext
    res = bearer(raw).post("/api/v1/jobs", {"media_id": str(make_media(user).pk), "models": [other],
                                            "audit_steps": ["fas"]}, format="json")
    assert res.status_code == 202, res.content
    job = Job.objects.get(pk=res.json()["jobs"][0]["id"])
    assert job.models_selected == [chosen] and job.audit_steps == ["metadata"]  # the admin's set, not the caller's
    detail = json.dumps(bearer(raw).get(f"/api/v1/jobs/{job.pk}").json())
    assert chosen not in detail and other not in detail and "models" not in res.json()["jobs"][0]
