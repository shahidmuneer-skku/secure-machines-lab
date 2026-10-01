"""Image studio (owner, 2026-10-01): generation and editing with the admin's model, charged per
delivered image, with consent for faces and a content filter."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from sml.core.models import PlatformSettings
from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind
from sml.jobs.dispatcher import dispatch_pending, envelope
from sml.jobs.models import Job, JobTask
from sml.media.models import MediaObject
from sml.queues import STUDIO
from sml.studio import services

URL = "/api/v1/studio/jobs"


def post(api: Any, **body: Any) -> Any:
    return api.post(URL, {"mode": "generate", "prompt": "A red fox in the snow", **body}, format="json",
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))


@pytest.fixture
def funded(user):  # type: ignore[no-untyped-def]
    credits.grant(user, 30, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    return user


@pytest.fixture
def staff_api(make_user, client_for):  # type: ignore[no-untyped-def]
    admin = make_user(roles=("admin",))
    credits.grant(admin, 30, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    return client_for(admin, mfa=True)


def outputs(n: int) -> list[dict[str, Any]]:
    return [{"id": str(uuid.uuid4()), "storage_key": f"media/u/x/{uuid.uuid4()}.png", "thumbnail_key": "",
             "content_type": "image/png", "size_bytes": 1000, "sha256": "ab", "width": 1328, "height": 1328,
             "seed": 7 + i} for i in range(n)]


def finish(worker: Any, job_id: str, *, result: dict[str, Any] | None = None, error: str = "") -> Job:
    dispatch_pending()
    task = JobTask.objects.get(job_id=job_id)
    worker.start(task)
    if error:
        worker.fail(task, error, "detail for staff")
    else:
        worker.succeed(task, result)
    return Job.objects.get(pk=job_id)


def test_the_studio_adapts_to_the_admins_model_and_hides_it_from_users(api, staff_api):
    cfg = api.get("/api/v1/studio/config").json()
    assert cfg["enabled"] and cfg["modes"]["generate"]["price"] == 3 and cfg["modes"]["edit"]["price"] == 2
    generate = cfg["modes"]["generate"]["controls"]  # Qwen-Image 2512 by default
    assert generate["references"] == {"min": 0, "max": 0} and generate["negative_prompt"]
    assert generate["aspect_ratios"][0] == {"id": "1:1", "width": 1328, "height": 1328}
    edit = cfg["modes"]["edit"]["controls"]  # Qwen-Image-Edit 2511
    assert edit["references"] == {"min": 1, "max": 3} and edit["match_input"] and not edit["transparent"]
    assert "models" not in cfg and "active" not in cfg
    staff = staff_api.get("/api/v1/studio/config").json()
    assert {m["id"] for m in staff["models"]} >= {"qwen-image-2.1", "flux2-klein-4b"}
    assert staff["active"] == {"generate": "qwen-image-2512", "edit": "qwen-image-edit-2511"}


def test_a_generation_reserves_credits_per_image_and_queues_for_the_studio(api, funded):
    res = post(api, count=3, seed=42, aspect_ratio="16:9", negative_prompt="blurry")
    assert res.status_code == 202, res.json()
    body = res.json()
    assert body["status"] == "queued" and body["mode"] == "generate" and body["credits_quoted"] == 9
    assert body["model"] is None  # users never see the model
    job = Job.objects.get(pk=body["id"])
    assert job.kind == Job.Kind.STUDIO and job.hold.amount == 9
    dispatch_pending()
    task = job.tasks.get()
    assert task.queue == STUDIO and task.target == "qwen-image-2512" and task.status == JobTask.Status.DISPATCHED
    env = envelope(task)
    assert env["kind"] == "studio" and env["studio"]["prompt"] == "A red fox in the snow"
    assert (env["studio"]["width"], env["studio"]["height"], env["studio"]["seed"]) == (1664, 928, 42)
    assert env["studio"]["negative_prompt"] == "blurry" and env["studio"]["references"] == []
    assert env["studio"]["safety_model"] == PlatformSettings.load().reasoning_model


@pytest.mark.parametrize("body, message", [
    ({"mode": "edit"}, "reference"),
    ({"aspect_ratio": "5:1"}, "format"),
    ({"transparent": True}, "Transparent"),
    ({"count": 5}, "between 1 and 4"),
    ({"steps": 500}, "Steps"),
    ({"model": "flux2-klein-4b"}, "administrators"),
    ({"prompt": "   "}, "prompt"),
])
def test_requests_outside_the_models_controls_are_refused(api, funded, body, message):
    res = post(api, **body)
    assert res.status_code == 400 and message.lower() in str(res.json()).lower(), res.json()
    assert not Job.objects.filter(kind=Job.Kind.STUDIO).exists()


def test_staff_can_try_another_model(staff_api):
    res = post(staff_api, model="qwen-image-2.1", transparent=True, aspect_ratio="1:1")
    assert res.status_code == 202, res.json()
    assert res.json()["model"] == {"id": "qwen-image-2.1", "name": "Qwen-Image 2.1"}
    assert Job.objects.get(pk=res.json()["id"]).options["studio"]["transparent"] is True


def test_only_delivered_images_are_charged_and_become_the_users_media(api, funded, worker):
    job_id = post(api, count=3).json()["id"]
    job = finish(worker, job_id, result={"outputs": outputs(2), "blocked": 1, "seed": 7})
    assert job.status == Job.Status.SUCCEEDED and job.credits_charged == 6  # 2 of 3 images × 3 credits
    assert credits.get_balance(funded).balance == 24
    images = list(MediaObject.objects.filter(generated_by=job))
    assert len(images) == 2 and all(m.owner == funded and m.status == MediaObject.Status.READY for m in images)
    body = api.get(f"{URL}/{job_id}").json()
    assert body["blocked"] == 1 and [o["seed"] for o in body["outputs"]] == [7, 8]
    assert body["outputs"][0]["download_url"].endswith("/content?download=1")
    public = [e.public_message for e in job.events.all()]
    assert "1 image withheld by the safety filter — not charged" in public
    assert "3 credits returned to your balance" in public


@pytest.mark.parametrize("code", ["PROMPT_BLOCKED", "OUTPUT_BLOCKED", "CONSENT_REQUIRED", "GPU_UNSUPPORTED"])
def test_refused_or_failed_requests_are_not_charged(api, funded, worker, code):
    job_id = post(api, count=2).json()["id"]
    job = finish(worker, job_id, error=code)
    assert job.status == Job.Status.FAILED and job.credits_charged == 0 and job.error_code == code
    assert credits.get_balance(funded).balance == 30
    error = api.get(f"{URL}/{job_id}").json()["error"]
    assert error["code"] == code and "not charged" in error["message"] and "detail for staff" not in error["message"]


def test_consent_for_faces_is_logged_with_the_job(api, funded, make_media):
    ref = make_media(funded)
    res = post(api, mode="edit", prompt="Make it a watercolour painting", reference_ids=[str(ref.pk)], consent=True)
    assert res.status_code == 202, res.json()
    job = Job.objects.get(pk=res.json()["id"])
    consent = job.options["consent"]
    assert consent["confirmed"] is True and consent["statement_version"] == services.CONSENT_VERSION
    assert job.events.filter(code="studio.consent").exists()
    assert job.credits_quoted == 2 and job.media == ref
    dispatch_pending()
    env = envelope(job.tasks.get())
    assert env["studio"]["consent"] is True
    assert env["studio"]["references"] == [{"storage_key": ref.storage_key, "extension": ref.extension}]


def test_references_must_be_the_users_own_images(api, funded, make_user, make_media):
    other = make_media(make_user())
    res = post(api, mode="edit", prompt="Make it blue", reference_ids=[str(other.pk)])
    assert res.status_code == 400 and "Unknown media" in str(res.json())


def test_studio_jobs_stay_out_of_the_detection_results_list(api, funded):
    job_id = post(api).json()["id"]
    assert job_id not in [j["id"] for j in api.get("/api/v1/jobs").json()["results"]]
    assert job_id in [j["id"] for j in api.get("/api/v1/jobs?kind=studio").json()["results"]]
    assert [j["id"] for j in api.get(URL).json()["results"]] == [job_id]


def test_admin_chooses_the_model_per_mode_and_the_studio_keeps_it_loaded(staff_api, monkeypatch):
    kept: list[list[str]] = []
    monkeypatch.setattr("sml.studio.services.publish_keep", lambda ids: kept.append(list(ids)))
    res = staff_api.patch("/api/v1/admin/studio", {"edit_model": "qwen-image-2.1"}, format="json")
    assert res.status_code == 200, res.json()
    assert res.json()["edit_model"] == "qwen-image-2.1" and kept[-1] == ["qwen-image-2512", "qwen-image-2.1"]
    assert staff_api.patch("/api/v1/admin/studio", {"edit_model": "qwen-image-2512"},
                           format="json").status_code == 400  # a text-to-image model cannot edit
    staff_api.patch("/api/v1/admin/studio", {"generate_model": ""}, format="json")
    assert kept[-1] == ["qwen-image-2.1"]
    assert staff_api.get("/api/v1/studio/config").json()["modes"]["generate"]["available"] is False


def test_a_disabled_studio_refuses_new_jobs(api, funded):
    cfg = PlatformSettings.load()
    cfg.studio_enabled = False
    cfg.save()
    assert api.get("/api/v1/studio/config").json()["enabled"] is False
    assert post(api).status_code == 503


def test_purging_a_studio_job_removes_its_images_unless_another_job_uses_them(api, funded, worker, make_media):
    from sml.jobs import services as job_services
    from sml.jobs.retention_tasks import purge_job_files

    ref = make_media(funded)
    job_id = post(api, mode="edit", prompt="Add a hat", reference_ids=[str(ref.pk)]).json()["id"]
    job = finish(worker, job_id, result={"outputs": outputs(2), "blocked": 0})
    kept, gone = list(job.outputs.order_by("original_name"))
    # The user analyses one of the images it made.
    detection = job_services.create_job(funded, job_services.JobRequest(media=kept))
    purge_job_files(job)
    kept.refresh_from_db(), gone.refresh_from_db(), ref.refresh_from_db()
    assert gone.status == MediaObject.Status.DELETED and ref.status == MediaObject.Status.DELETED
    assert kept.status == MediaObject.Status.READY and detection.media == kept
