"""Users see the verdict and its evidence, never which detectors run or how (owner's rule).

Covers the user API (job detail and list, live events, artifacts, reports, explanations,
catalog), what the admin chooses (detectors per media type, extra checks), and the metadata
rule for AI-generation markers.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from sml.catalog.registry import registry
from sml.core.events import memory_events
from sml.credits import services as credits
from sml.credits.models import CreditSource, LedgerKind
from sml.jobs import explain, services
from sml.jobs.dispatcher import dispatch_pending
from sml.jobs.models import Job, JobTask
from sml.jobs.results import record_task_event
from sml.reports import generators
from sml.reports.services import build_data

pytestmark = pytest.mark.django_db

STRONG = {"ai_generated": True, "confidence": "strong",
          "evidence": [{"source": "C2PA", "strength": "strong", "detail": "Content Credentials declare AI"}],
          "exief": {"status": "ok", "verdict": "confirmed", "score": 108, "untrustworthy": [], "signals": []}}
WEAK = {"ai_generated": False, "confidence": "weak",
        "evidence": [{"source": "Metadata text", "strength": "weak", "detail": "Mentions Midjourney"}],
        "exief": {"status": "ok", "verdict": "weak", "score": 27, "untrustworthy": [], "signals": []}}


def plain_image_detectors(n: int = 2) -> list[str]:
    return [m.id for m in registry().enabled_for("image") if not m.fallbacks][:n]


def detector_images(job: Job, task: JobTask) -> list[dict[str, Any]]:
    """What detectors typically write: the input, a blended map, a raw map, a face map, per-frame data."""
    key = f"jobs/{job.pk}/{task.target}"
    return [
        {"kind": "xai", "label": "Original", "content_type": "image/png", "storage_key": f"{key}_original.png"},
        {"kind": "xai", "label": "gradcam heatmap", "content_type": "image/png", "storage_key": f"{key}_heat.png"},
        {"kind": "xai", "label": "Grad-CAM", "content_type": "image/png", "storage_key": f"{key}_gradcam.png"},
        {"kind": "face", "label": "face attention", "content_type": "image/png", "storage_key": f"{key}_face.png"},
        {"kind": "frames", "label": "Per-frame scores", "content_type": "text/csv", "storage_key": f"{key}_frames.csv"},
    ]


@pytest.fixture
def finished_job(user, make_media, use_detectors, show_heatmaps):  # type: ignore[no-untyped-def]
    """A finished image job with two detectors; users see the first detector's heatmap."""
    def make(prob: float = 0.9, indicators: dict[str, Any] | None = None) -> Job:
        credits.grant(user, 10, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
        use_detectors(plain_image_detectors())
        show_heatmaps(plain_image_detectors()[:1])
        job = services.create_job(user, services.JobRequest(media=make_media(user)))
        dispatch_pending()
        for task in job.tasks.all():
            record_task_event({"event": "started", "task_id": str(task.pk), "attempt": 1, "gpu": "0"})
        for task in job.tasks.all():
            if task.kind == JobTask.Kind.AUDIT:
                result: dict[str, Any] = {"ai_indicators": indicators or {}}
                artifacts: list[dict[str, Any]] = []
            else:
                result = {"fake_prob": prob}
                artifacts = detector_images(job, task)
            record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk), "attempt": 1,
                               "result": result, "artifacts": artifacts})
        job.refresh_from_db()
        return job

    return make


def detector_words(job: Job) -> set[str]:
    reg = registry()
    words = set()
    for t in job.tasks.filter(kind=JobTask.Kind.MODEL):
        words |= {t.target, reg.get(t.target).name("en")}
    return words


def test_the_user_view_never_names_detectors(api, user, finished_job):
    job = finished_job()
    assert job.status == Job.Status.SUCCEEDED
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    listing = api.get("/api/v1/jobs").json()
    text = json.dumps([detail, listing])
    for word in detector_words(job):
        assert word not in text, word
    for key in ("tasks", "summary", "models", "audit_steps"):
        assert key not in detail
    assert [s["id"] for s in detail["steps"]] == ["queued", "checks", "analysis", "results"]
    assert all(s["status"] == "done" for s in detail["steps"])
    assert detail["verdict"] == "fake" and detail["fake_probability"] == pytest.approx(0.9)
    assert detail["verdict_reasons"][0]["code"] == "analysis"
    # One heatmap — the chosen detector's blended map — and nothing else (no raw maps, faces or CSVs).
    assert [a["label"] for a in detail["artifacts"]] == ["heatmap"]
    chosen = job.artifacts.get(pk=detail["artifacts"][0]["id"])
    assert chosen.storage_key.endswith(f"{plain_image_detectors()[0]}_gradcam.png")


def test_staff_still_see_everything(client_for, make_user, finished_job):
    job = finished_job()
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    detail = admin.get(f"/api/v1/admin/jobs/{job.pk}").json()
    assert {t["target"] for t in detail["tasks"] if t["kind"] == "model"} == set(plain_image_detectors())
    assert any("started" in e["message"] for e in detail["events"])
    task = job.tasks.filter(kind=JobTask.Kind.MODEL).first()
    assert admin.get(f"/api/v1/admin/jobs/{job.pk}/tasks/{task.pk}/log").status_code == 200


def test_live_events_and_the_timeline_are_generic(api, finished_job):
    job = finished_job()
    words = detector_words(job)
    live = json.dumps([payload for _, payload in memory_events])
    assert not any(w in live for w in words)
    messages = [e["message"] for e in api.get(f"/api/v1/jobs/{job.pk}").json()["events"]]
    assert "Checking file metadata and provenance" in messages
    assert messages.count("Analysing the image") == 1  # once, however many detectors run
    assert not any(w in m for m in messages for w in words)


def test_artifacts_download_only_as_generic_evidence(api, finished_job, monkeypatch):
    from django.http import HttpResponse

    from sml.jobs import views

    served: list[str] = []

    def fake_serve(key, *, content_type, filename):  # type: ignore[no-untyped-def]
        served.append(filename)
        return HttpResponse(b"x", content_type=content_type)

    monkeypatch.setattr(views, "serve_object", fake_serve)
    job = finished_job()
    heatmap = job.artifacts.get(storage_key__endswith=f"{plain_image_detectors()[0]}_gradcam.png")
    frames = job.artifacts.filter(kind="frames").first()
    assert api.get(f"/api/v1/jobs/{job.pk}/artifacts/{heatmap.pk}/content").status_code == 200
    assert served[0].startswith("heatmap-") and plain_image_detectors()[0] not in served[0]
    assert api.get(f"/api/v1/jobs/{job.pk}/artifacts/{frames.pk}/content").status_code == 404
    assert api.get(f"/api/v1/jobs/{job.pk}/tasks/{job.tasks.first().pk}/log").status_code == 404


def test_reports_and_the_explanation_prompt_never_name_detectors(finished_job):
    job = finished_job(indicators=STRONG)
    words = detector_words(job)
    data = build_data(job, "en")
    csv_text = generators.render_csv(data).decode("utf-8")
    rtf = generators.render_hwp(data).decode("ascii")
    assert not any(w in csv_text or w in rtf for w in words)
    assert "Likely AI-generated" in rtf and "Content Credentials declare AI" in csv_text
    context = explain._context(job)
    # Storage keys only tell the worker what to download; the agent sees the files as heatmap_N.png.
    readable = json.dumps({k: v for k, v in context.items() if k != "artifacts"})
    assert not any(w in readable for w in words) and "summary" not in context
    assert {a["kind"] for a in context["artifacts"]} == {"heatmap"}


def test_detector_catalogs_are_not_public(api, client):  # type: ignore[no-untyped-def]
    assert api.get("/api/v1/catalog/models").status_code == 404
    assert client.get("/api/v1/catalog/public-models").status_code == 404
    assert api.get("/api/v1/catalog/modules").status_code == 200
    schema = json.loads(client.get("/api/openapi.json", {"format": "json"}).content)
    assert "/api/v1/jobs" in schema["paths"] and not any(p.startswith("/api/v1/admin/") for p in schema["paths"])
    assert "AdminModel" not in schema["components"]["schemas"]


# --- what runs is the admin's choice ----------------------------------------------------------

def test_admin_sets_detectors_per_media_type_and_extra_checks(client_for, make_user, user, make_media):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    image_only = next(m for m in registry().enabled_for("image") if not m.supports("video"))
    a, b = plain_image_detectors()
    for spec in registry().enabled_for("image"):
        res = admin.patch("/api/v1/admin/models", {"model_id": spec.id, "run_on_image": spec.id in (a, b)},
                          format="json")
        assert res.status_code == 200, res.content
    bad = admin.patch("/api/v1/admin/models", {"model_id": image_only.id, "run_on_video": True}, format="json")
    assert bad.status_code == 400
    setup = admin.patch("/api/v1/admin/models/setup", {"audit_steps": ["face", "safety"]}, format="json")
    assert setup.status_code == 200, setup.content
    assert {c["id"] for c in setup.json()["checks"] if c["enabled"]} == {"metadata", "face", "safety"}
    assert admin.patch("/api/v1/admin/models/setup", {"audit_steps": ["xray"]}, format="json").status_code == 400

    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    job = services.create_job(user, services.JobRequest(media=make_media(user)))
    assert sorted(job.models_selected) == sorted([a, b])
    assert job.audit_steps == ["metadata", "face", "safety"]


def test_users_cannot_configure_detection(client_for, make_user):
    support = client_for(make_user(roles=("support",)), mfa=True)
    assert support.patch("/api/v1/admin/models/setup", {"audit_steps": []}, format="json").status_code == 403


def test_no_configured_detector_gives_a_generic_error(user, make_media, use_detectors):
    use_detectors([])
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    with pytest.raises(Exception, match="not available for your account"):
        services.create_job(user, services.JobRequest(media=make_media(user)))


# --- metadata markers (EXIEF weighs into the AI-generation analysis; test_exief_vote.py) ---------

@pytest.mark.parametrize(("indicators", "flagged"), [(STRONG, True), (WEAK, False), ({}, False)])
def test_metadata_evidence_is_shown_and_only_a_declaration_reads_ai_generated(api, finished_job, indicators,
                                                                               flagged):
    job = finished_job(prob=0.9, indicators=indicators)
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    assert (detail["verdict"], detail["ai_generated"]) == ("fake", flagged)
    assert (detail["verdict_label"] == "Likely AI-generated") is flagged
    if indicators:
        assert detail["provenance"]["evidence"][0]["detail"] == indicators["evidence"][0]["detail"]
    assert "exief" not in json.dumps(detail).lower()  # the tool behind the evidence is not named


def test_the_admin_chooses_whose_heatmaps_users_see(api, user, make_media, use_detectors, show_heatmaps, platform):
    platform.free_max_inflight_tasks = 20  # dispatch every detector at once
    platform.save()
    ids = [m.id for m in registry().enabled_for("image") if not m.fallbacks][:4]
    use_detectors(ids)
    show_heatmaps(ids[1:3])
    credits.grant(user, 5, source=CreditSource.PURCHASE, kind=LedgerKind.PURCHASE)
    job = services.create_job(user, services.JobRequest(media=make_media(user)))
    dispatch_pending()
    for task in job.tasks.all():
        record_task_event({"event": "started", "task_id": str(task.pk), "attempt": 1})
        model = task.kind == JobTask.Kind.MODEL
        record_task_event({"event": "finished", "status": "succeeded", "task_id": str(task.pk), "attempt": 1,
                           "result": {"fake_prob": 0.7} if model else {},
                           "artifacts": detector_images(job, task) if model else []})
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    shown = [job.artifacts.get(pk=a["id"]).storage_key for a in detail["artifacts"]]
    assert sorted(shown) == sorted(f"jobs/{job.pk}/{m}_gradcam.png" for m in ids[1:3])
    hidden = job.artifacts.exclude(pk__in=[a["id"] for a in detail["artifacts"]]).filter(kind="xai").first()
    assert api.get(f"/api/v1/jobs/{job.pk}/artifacts/{hidden.pk}/content").status_code == 404

    show_heatmaps([])
    assert api.get(f"/api/v1/jobs/{job.pk}").json()["artifacts"] == []


def test_admin_toggles_heatmaps_per_detector(client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    model = plain_image_detectors()[0]
    res = admin.patch("/api/v1/admin/models", {"model_id": model, "show_heatmap": True}, format="json")
    assert res.status_code == 200, res.content
    listed = {m["id"]: m for m in admin.get("/api/v1/admin/models").json()}
    assert listed[model]["show_heatmap"] is True
    assert listed["center"]["show_heatmap"] is True  # owner's default (models.yaml)
