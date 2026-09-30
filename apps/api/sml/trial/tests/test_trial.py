"""Guest trial: daily allowance per device and network, images only, results only for the same device."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from sml.jobs.models import Job

pytestmark = pytest.mark.django_db


def guest() -> APIClient:
    client = APIClient()
    client.get("/api/v1/trial/status")  # issues the signed device cookie
    return client


def detect(client: APIClient, png_upload, ip: str = "203.0.113.7"):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/trial/detect", {"file": png_upload()}, format="multipart", REMOTE_ADDR=ip)


def test_status_reports_the_admin_configured_allowance(platform):
    platform.guest_trial_images_per_day = 3
    platform.save()
    res = APIClient().get("/api/v1/trial/status")
    assert res.status_code == 200
    assert res.json()["remaining"] == 3


def test_allowance_runs_out_per_device(platform, png_upload):
    platform.guest_trial_images_per_day = 2
    platform.save()
    client = guest()
    first = detect(client, png_upload)
    assert first.status_code == 202, first.content
    assert first.json()["remaining"] == 1
    assert detect(client, png_upload).status_code == 202
    blocked = detect(client, png_upload)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "TRIAL_EXHAUSTED"
    job = Job.objects.get(pk=first.json()["job_id"])
    assert job.user_id is None and job.source == Job.Source.TRIAL and job.credits_quoted == 0


def test_new_cookies_from_the_same_network_are_capped(platform, png_upload):
    platform.guest_trial_images_per_day = 1
    platform.save()
    statuses = [detect(guest(), png_upload, ip="198.51.100.20").status_code for _ in range(6)]
    assert statuses.count(202) < 6
    assert statuses[-1] == 429


def test_only_the_same_device_can_see_the_result(platform, png_upload):
    platform.guest_trial_images_per_day = 3
    platform.save()
    owner = guest()
    job_id = detect(owner, png_upload).json()["job_id"]
    assert owner.get(f"/api/v1/trial/jobs/{job_id}").status_code == 200
    assert guest().get(f"/api/v1/trial/jobs/{job_id}").status_code == 404


def test_disabled_trial_allows_nothing(platform, png_upload):
    platform.guest_trial_enabled = False
    platform.save()
    assert detect(guest(), png_upload).status_code == 429
