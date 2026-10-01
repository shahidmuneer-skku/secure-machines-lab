"""Long-form streaming scans: reservation, live events, per-minute settlement, expiry."""

from __future__ import annotations

import base64
import io
from datetime import timedelta

import pytest
from django.utils import timezone
from PIL import Image

from sml.core.exceptions import ApiError, Conflict, InsufficientCredits
from sml.credits import services as credits
from sml.credits.models import CreditHold, CreditSource, LedgerKind
from sml.jobs import streams
from sml.jobs.models import Artifact, Job, JobTask, StreamSession

pytestmark = pytest.mark.django_db

CATALOG = [
    {"model_id": "skku-aigc", "name": "SKKU-AIGC", "available": True, "reason": "",
     "face_crop": {"support": "optional", "default": False}},
    {"model_id": "skku-p2", "name": "SKKU-P2", "available": False, "reason": "missing env",
     "face_crop": {"support": "optional", "default": True}},
]
# Golden vector shared with apps/stream/tests/test_tokens.py: both sides must agree byte for byte.
GOLDEN_CLAIMS = {"sid": "s-1", "exp": 2000000000, "model": "skku-aigc", "max_seconds": 90.0}
GOLDEN_TOKEN = ("eyJleHAiOjIwMDAwMDAwMDAsIm1heF9zZWNvbmRzIjo5MC4wLCJtb2RlbCI6InNra3UtYWlnYyIsInNpZCI6InMtMSJ9"
                "." "0c11f53e74bb1aab76c7e0118a21ae5a8df008b99dc895b98b4b332048f0e218")


@pytest.fixture(autouse=True)
def catalog(monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(streams, "available_models", lambda use_cache=True: CATALOG)


def fund(user, amount: int = 100) -> None:  # type: ignore[no-untyped-def]
    credits.grant(user, amount, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)


def request(**overrides):  # type: ignore[no-untyped-def]
    data = {"file_name": "interview.mp4", "file_size": 50_000_000,
            "duration_seconds": 600.0, "start_seconds": 60.0, "end_seconds": 360.0, "interval_seconds": 5.0}
    return streams.StreamRequest(**{**data, **overrides})


def preview() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (32, 18), (10, 20, 30)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def rows(start: float, count: int, step: float = 5.0, prob: float = 0.8) -> list[dict]:
    return [{"index": i, "start_sec": start + i * step, "end_sec": start + (i + 1) * step,
             "fake_probability": prob, "frames_used": 8} for i in range(count)]


def test_golden_token_matches_the_stream_service():
    assert streams.sign_token(GOLDEN_CLAIMS) == GOLDEN_TOKEN


def test_session_reserves_the_selected_range_per_started_minute(user):
    fund(user)
    session, token = streams.create_session(user, request())
    job = session.job
    assert session.reserved_seconds == 300.0
    assert job.credits_quoted == 20  # 5 minutes x 4 credits
    assert job.hold.amount == 20 and job.media is None and job.options["stream"] is True
    task = job.tasks.get()
    assert (task.kind, task.status, task.queue) == (JobTask.Kind.LONG_VIDEO, JobTask.Status.DISPATCHED, "stream")
    assert task.target == "skku-aigc"  # the first available detector, chosen by the admin (empty setting)
    body = base64.urlsafe_b64decode(token.split(".")[0] + "==").decode()
    assert "skku" not in body.lower() and str(session.pk) in body  # the browser's token names the session only


def test_the_admin_chooses_the_long_form_detector(user, platform):
    fund(user)
    platform.long_video_model = "skku-p2"  # offered but unavailable (missing env)
    platform.long_video_face_crops = {"skku-p2": False, "skku-aigc": True}  # set per detector
    platform.save()
    with pytest.raises(ApiError, match="not available right now"):
        streams.create_session(user, request())
    CATALOG[1]["available"] = True
    try:
        session, _ = streams.create_session(user, request())
    finally:
        CATALOG[1]["available"] = False
    assert (session.model_id, session.face_crop) == ("skku-p2", False)


def test_a_session_is_claimed_once_by_the_stream_service(user, client_for):
    fund(user)
    session, _ = streams.create_session(user, request())
    url = f"/api/internal/streams/{session.pk}/claim"
    service = client_for()
    assert service.post(url, format="json").status_code == 403
    first = service.post(url, format="json", HTTP_X_STREAM_KEY="test-stream-secret")
    assert first.status_code == 200, first.content
    assert first.json()["model"] == "skku-aigc" and first.json()["max_seconds"] == 300.0
    assert service.post(url, format="json", HTTP_X_STREAM_KEY="test-stream-secret").status_code == 409


@pytest.mark.parametrize(("overrides", "message"), [
    ({"start_seconds": 700.0}, "start time"),
    ({"end_seconds": 30.0}, "end time"),
    ({"interval_seconds": 0.1}, "interval"),
])
def test_invalid_requests_are_rejected_before_charging(user, overrides, message):
    fund(user)
    with pytest.raises(ApiError, match=message):
        streams.create_session(user, request(**overrides))
    assert not Job.objects.exists()
    assert credits.get_balance(user).balance == 100


def test_insufficient_credits(user):
    fund(user, 5)
    with pytest.raises(InsufficientCredits):
        streams.create_session(user, request())
    assert not StreamSession.objects.exists()


def start(session):  # type: ignore[no-untyped-def]
    return streams.handle_event(str(session.pk), {
        "event": "started", "duration": 600.0, "width": 1280, "height": 720, "fps": 25.0,
        "start_sec": 60.0, "end_sec": 360.0, "preview_jpeg": preview()})


def test_full_scan_is_charged_per_minute_analysed(user):
    fund(user)
    session, _ = streams.create_session(user, request())
    start(session)
    task = session.job.tasks.get()
    assert task.status == JobTask.Status.RUNNING
    assert Artifact.objects.filter(job=session.job, meta__preview=True).exists()
    streams.handle_event(str(session.pk), {"event": "intervals", "intervals": rows(60.0, 10), "total": 60})
    task.refresh_from_db()
    assert len(task.result["intervals"]) == 10 and task.progress == pytest.approx(100 * 10 / 60)
    result = streams.handle_event(str(session.pk), {
        "event": "finished", "status": "done", "intervals": rows(60.0, 60), "average": 0.8})
    job = Job.objects.get(pk=session.job_id)
    assert result["credits_charged"] == 20 and job.credits_charged == 20
    assert (job.status, job.verdict, job.partial) == (Job.Status.SUCCEEDED, Job.Verdict.FAKE, False)
    assert job.summary["groups"] == [{"group": "ai_generated", "status": "done", "fake_probability": 0.8,
                                      "verdict": Job.Verdict.FAKE}]  # the detector's analysis
    assert job.hold.status == CreditHold.Status.CAPTURED
    assert credits.get_balance(user).balance == 80
    assert credits.verify_wallet(credits.ensure_wallet(user))


def test_stopped_scan_pays_only_the_minutes_analysed(user):
    fund(user)
    session, _ = streams.create_session(user, request())
    start(session)
    result = streams.handle_event(str(session.pk), {
        "event": "finished", "status": "stopped", "intervals": rows(60.0, 25), "average": 0.2})  # 125 s
    job = Job.objects.get(pk=session.job_id)
    assert result["credits_charged"] == 12  # 3 started minutes x 4
    assert (job.status, job.verdict, job.partial) == (Job.Status.SUCCEEDED, Job.Verdict.REAL, True)
    assert credits.get_balance(user).balance == 88
    assert credits.verify_wallet(credits.ensure_wallet(user))


@pytest.mark.parametrize(("status", "job_status"), [("error", Job.Status.FAILED), ("stopped", Job.Status.CANCELED)])
def test_no_results_means_no_charge(user, status, job_status):
    fund(user)
    session, _ = streams.create_session(user, request())
    start(session)
    streams.handle_event(str(session.pk), {"event": "finished", "status": status, "intervals": [],
                                           "error": "Traceback /home/ops/secret.py"})
    job = Job.objects.get(pk=session.job_id)
    assert job.status == job_status and job.credits_charged == 0
    assert credits.get_balance(user).balance == 100
    if status == "error":
        task = job.tasks.get()
        assert "/home/ops" in task.error_detail and "/home/ops" not in task.error_message


def test_events_after_the_end_are_refused(user):
    fund(user)
    session, _ = streams.create_session(user, request())
    start(session)
    streams.handle_event(str(session.pk), {"event": "finished", "status": "done", "intervals": rows(60, 2)})
    with pytest.raises(Conflict):
        streams.handle_event(str(session.pk), {"event": "intervals", "intervals": rows(70, 1)})


def test_cancel_from_the_job_page_stops_the_stream_and_charges_what_ran(user):
    from sml.jobs import services

    fund(user)
    session, _ = streams.create_session(user, request())
    start(session)
    services.cancel_job(session.job)
    with pytest.raises(Conflict):
        streams.handle_event(str(session.pk), {"event": "intervals", "intervals": rows(60.0, 12)})
    result = streams.handle_event(str(session.pk), {"event": "finished", "status": "stopped",
                                                    "intervals": rows(60.0, 12), "average": 0.4})
    assert result["credits_charged"] == 4  # 60 s analysed = 1 minute


def test_cancel_before_the_upload_releases_everything(user):
    from sml.jobs import services

    fund(user)
    session, _ = streams.create_session(user, request())
    job = services.cancel_job(session.job)
    assert job.status == Job.Status.CANCELED
    assert credits.get_balance(user).balance == 100
    with pytest.raises(Conflict):
        start(session)


def test_internal_endpoint_requires_the_service_key(user, client_for):
    fund(user)
    session, _ = streams.create_session(user, request())
    url = f"/api/internal/streams/{session.pk}/events"
    anonymous = client_for()
    assert anonymous.post(url, {"event": "started"}, format="json").status_code == 403
    assert anonymous.post(url, {"event": "started"}, format="json", HTTP_X_STREAM_KEY="wrong").status_code == 403
    ok = anonymous.post(url, {"event": "started", "start_sec": 60, "end_sec": 360}, format="json",
                        HTTP_X_STREAM_KEY="test-stream-secret")
    assert ok.status_code == 200, ok.content


def test_session_endpoint_returns_a_token_for_the_browser(api, user):
    fund(user)
    res = api.post("/api/v1/long-video/sessions", {
        "file_name": "clip.mp4", "file_size": 1_000_000, "duration_seconds": 42.0}, format="json")
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["ws_url"] == "ws://stream.test/stream/ws" and body["credits_reserved"] == 4
    config = api.get("/api/v1/long-video/config").json()
    assert config == {"online": True, "available": True, "price_per_minute": 4, "max_bytes": config["max_bytes"],
                      "max_seconds": config["max_seconds"]}
    assert api.get("/api/v1/long-video/models").status_code == 404  # detectors are not listed to users


def test_stale_sessions_are_refunded(user):
    from django.conf import settings

    fund(user)
    never_uploaded, _ = streams.create_session(user, request())
    went_silent, _ = streams.create_session(user, request(file_name="b.mp4"))
    start(went_silent)
    StreamSession.objects.filter(pk=never_uploaded.pk).update(
        created_at=timezone.now() - timedelta(minutes=settings.STREAM_UPLOAD_TIMEOUT_MINUTES + 1))
    StreamSession.objects.filter(pk=went_silent.pk).update(
        last_event_at=timezone.now() - timedelta(minutes=settings.STREAM_IDLE_TIMEOUT_MINUTES + 1))
    assert streams.expire_stale_sessions() == 2
    statuses = dict(Job.objects.values_list("title", "status"))
    assert statuses == {"interview.mp4": Job.Status.CANCELED, "b.mp4": Job.Status.FAILED}
    assert credits.get_balance(user).balance == 100


def test_worker_sweeps_leave_stream_tasks_alone(user):
    from sml.jobs.tasks import requeue_stale

    fund(user)
    session, _ = streams.create_session(user, request())
    JobTask.objects.filter(job=session.job).update(dispatched_at=timezone.now() - timedelta(days=3))
    assert requeue_stale() == 0


def test_face_cropping_is_set_per_long_form_detector(client_for, make_user, platform):
    CATALOG.append({"model_id": "beybi", "name": "SKKU (BEYBI)", "available": True, "reason": "",
                    "face_crop": {"support": "always", "default": True}})
    try:
        admin = client_for(make_user(roles=("admin",)), mfa=True)
        url = "/api/v1/admin/models/setup"
        res = admin.patch(url, {"long_video_face_crops": {"skku-aigc": True, "skku-p2": False}}, format="json")
        assert res.status_code == 200, res.content
        models = {m["model_id"]: m for m in res.json()["long_video"]["models"]}
        assert (models["skku-aigc"]["face_crop_setting"], models["skku-p2"]["face_crop_setting"]) == (True, False)
        assert models["beybi"]["face_crop_setting"] is None and models["beybi"]["face_crop"] == "always"
        # A detector that always crops cannot be switched; null returns one to its default.
        assert admin.patch(url, {"long_video_face_crops": {"beybi": False}}, format="json").status_code == 400
        admin.patch(url, {"long_video_face_crops": {"skku-p2": None}}, format="json")
        platform.refresh_from_db()
        assert platform.long_video_face_crops == {"skku-aigc": True}
    finally:
        CATALOG.pop()
