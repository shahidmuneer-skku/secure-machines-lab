"""Results per analysis (face swap / AI generation) and the headline verdict (owner, 2026-10-01).

Users see one result per analysis — verdict and probability — and never how many detectors each
combines. The headline is fake when any analysis says fake and shows the highest probability.
"""

from __future__ import annotations

import json

import pytest

from sml.catalog.registry import registry

pytestmark = pytest.mark.django_db


def detectors(family: str, n: int) -> list[str]:
    ids = [m.id for m in registry().enabled_for("image") if m.family == family and not m.fallbacks
           and m.authentic_boost == 1 and not m.authentic_counts_in_all][:n]
    assert len(ids) == n, f"config/models.yaml needs {n} plain image detectors in {family}"
    return ids


def test_each_analysis_has_its_own_result_and_any_fake_flags_the_file(api, run_job):
    swap = detectors("deepfake", 2)
    aigc = detectors("ai_generated", 1)
    job = run_job({swap[0]: 0.9, swap[1]: 0.7, aigc[0]: 0.2})
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    analyses = {a["id"]: a for a in detail["analyses"]}
    assert set(analyses) == {"face_swap", "ai_generated"}
    assert analyses["face_swap"]["verdict"] == "fake"
    assert analyses["face_swap"]["fake_probability"] == pytest.approx(0.8)  # combined within the analysis
    assert (analyses["ai_generated"]["verdict"], analyses["ai_generated"]["fake_probability"]) == ("real", 0.2)
    assert (detail["verdict"], detail["fake_probability"]) == ("fake", pytest.approx(0.8))
    text = json.dumps(detail)
    assert not any(m in text for m in swap + aigc) and '"models"' not in text


def test_the_headline_is_authentic_only_when_every_analysis_is(api, run_job):
    job = run_job({detectors("deepfake", 1)[0]: 0.3, detectors("ai_generated", 1)[0]: 0.4})
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    assert detail["verdict"] == "real" and detail["fake_probability"] == pytest.approx(0.4)  # the higher one
    assert [a["id"] for a in detail["analyses"]] == ["face_swap", "ai_generated"]


def test_no_face_is_reported_for_the_face_swap_analysis_only(api, run_job):
    job = run_job({detectors("deepfake", 1)[0]: "no_face", detectors("ai_generated", 1)[0]: 0.1})
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    analyses = {a["id"]: a for a in detail["analyses"]}
    assert analyses["face_swap"] == {"id": "face_swap", "status": "no_face", "verdict": "no_face",
                                     "fake_probability": None}
    assert detail["verdict"] == "real" and analyses["ai_generated"]["verdict"] == "real"


def test_the_admin_can_move_a_detector_to_another_analysis(api, client_for, make_user, run_job):
    moved = detectors("ai_generated", 1)[0]
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    res = admin.patch("/api/v1/admin/models", {"model_id": moved, "family": "deepfake"}, format="json")
    assert res.status_code == 200, res.content
    for invalid in ("general", "xray"):  # there are two analyses only
        res = admin.patch("/api/v1/admin/models", {"model_id": moved, "family": invalid}, format="json")
        assert res.status_code == 400
    job = run_job({moved: 0.9})
    assert [a["id"] for a in api.get(f"/api/v1/jobs/{job.pk}").json()["analyses"]] == ["face_swap"]
    admin.patch("/api/v1/admin/models", {"model_id": moved, "family": ""}, format="json")  # back to models.yaml
    assert registry().get(moved).family == "ai_generated"


def test_every_detector_belongs_to_one_of_the_two_analyses():
    assert {m.family for m in registry().models.values()} == {"deepfake", "ai_generated"}


def test_older_jobs_with_a_general_analysis_show_only_the_two(api, run_job):
    job = run_job({detectors("deepfake", 1)[0]: 0.9})
    job.summary["groups"].append({"group": "general", "status": "done", "fake_probability": 0.1, "verdict": "real"})
    job.save(update_fields=["summary"])
    assert [a["id"] for a in api.get(f"/api/v1/jobs/{job.pk}").json()["analyses"]] == ["face_swap"]


def test_reports_list_the_analyses(run_job):
    from sml.reports import generators
    from sml.reports.services import build_data

    job = run_job({detectors("deepfake", 1)[0]: 0.9, detectors("ai_generated", 1)[0]: 0.2})
    data = build_data(job, "en")
    csv_text = generators.render_csv(data).decode("utf-8")
    rtf = generators.render_hwp(data).decode("ascii")
    assert "face_swap,fake,0.900000" in csv_text and "ai_generated,real,0.200000" in csv_text
    assert "Face-swap analysis: Likely manipulated" in rtf and "AI-generation analysis: Likely authentic" in rtf
