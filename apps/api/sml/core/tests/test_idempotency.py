"""Idempotency-Key: successful responses are stored for replay, whatever types they hold."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from sml.core.idempotency import idempotent
from sml.core.models import IdempotencyRecord
from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind

pytestmark = pytest.mark.django_db

ID = uuid.UUID("01a0fc24-d533-730e-9c06-ead9178e7c71")


class _Create(APIView):
    calls = 0

    @idempotent()
    def post(self, request):  # type: ignore[no-untyped-def]
        type(self).calls += 1
        # DRF renders these types; the stored replay copy must hold them too.
        return Response({"id": ID, "at": timezone.now(), "amount": Decimal("1.50")}, status=202)


def _post(user, key: str):  # type: ignore[no-untyped-def]
    request = APIRequestFactory().post("/api/v1/things", {"a": 1}, format="json", HTTP_IDEMPOTENCY_KEY=key)
    force_authenticate(request, user=user)
    return _Create.as_view()(request)


def test_a_response_with_uuids_dates_and_decimals_is_stored_and_replayed(user):
    _Create.calls = 0
    first = _post(user, "key-1")
    assert first.status_code == 202
    record = IdempotencyRecord.objects.get(key="key-1")
    assert record.response_status == 202
    # stored exactly as DRF rendered it to the client (decimals become numbers)
    assert record.response_body["id"] == str(ID) and record.response_body["amount"] == 1.5
    again = _post(user, "key-1")
    assert again.status_code == 202 and again["Idempotent-Replayed"] == "true"
    assert again.data["id"] == str(ID)
    assert _Create.calls == 1


def test_submitting_several_files_at_once_succeeds(api, user, make_media):
    """A batch's jobs carry a batch_id (a UUID): storing the replay copy used to fail with a 500."""
    credits.grant(user, 10, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    media = [make_media(user, name=f"photo-{i}.png") for i in range(2)]
    body = {"media_ids": [str(m.pk) for m in media]}
    res = api.post("/api/v1/jobs", body, format="json", HTTP_IDEMPOTENCY_KEY="batch-1")
    assert res.status_code == 202, res.content
    jobs = res.json()["jobs"]
    assert len(jobs) == 2 and jobs[0]["batch_id"] and jobs[0]["batch_id"] == jobs[1]["batch_id"]
    replay = api.post("/api/v1/jobs", body, format="json", HTTP_IDEMPOTENCY_KEY="batch-1")
    assert replay.status_code == 202 and replay["Idempotent-Replayed"] == "true"
    assert [j["id"] for j in replay.json()["jobs"]] == [j["id"] for j in jobs]
