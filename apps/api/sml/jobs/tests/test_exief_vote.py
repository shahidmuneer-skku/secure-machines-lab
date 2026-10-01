"""EXIEF metadata signals weigh into the AI-generation analysis (owner, 2026-10-01).

EXIEF votes like a detector of weight `exief_weight` (default 3): confirmed counts as 100% fake,
suspect 80%, weak 60%. "unknown" adds nothing (no signal is never proof of authenticity), and
metadata that is damaged or altered (ExifTool corruption, failed C2PA validation) is not counted.
The detectors keep counting; the face-swap analysis is unaffected.
"""

from __future__ import annotations

import pytest

from sml.catalog.registry import registry

pytestmark = pytest.mark.django_db


def plain(family: str, n: int) -> list[str]:
    ids = [m.id for m in registry().enabled_for("image") if m.family == family and not m.fallbacks
           and m.authentic_boost == 1 and not m.authentic_counts_in_all][:n]
    assert len(ids) == n
    return ids


def metadata(verdict: str, untrustworthy: list[str] | None = None) -> dict:
    return {"ai_generated": verdict == "confirmed" and not untrustworthy, "confidence": "strong",
            "evidence": [{"source": "Generator declaration", "strength": "strong",
                          "detail": "C2PA trainedAlgorithmicMedia — OpenAI Media Service API"}],
            "exief": {"status": "ok", "verdict": verdict, "score": 108, "untrustworthy": untrustworthy or [],
                      "signals": [{"id": "c2pa_trained", "label": "C2PA trainedAlgorithmicMedia", "tier": 1}]}}


def analyses(api, job) -> dict[str, dict]:  # type: ignore[no-untyped-def]
    return {a["id"]: a for a in api.get(f"/api/v1/jobs/{job.pk}").json()["analyses"]}


@pytest.mark.parametrize(("verdict", "expected", "label"), [
    ("confirmed", (0.2 + 0.3 + 3 * 1.0) / 5, "Likely AI-generated"),  # 0.70
    ("suspect", (0.2 + 0.3 + 3 * 0.8) / 5, "Likely manipulated / AI-generated"),  # 0.58
    ("weak", (0.2 + 0.3 + 3 * 0.6) / 5, "Likely authentic"),  # 0.46: outvoted by the detectors
    ("unknown", (0.2 + 0.3) / 2, "Likely authentic"),  # no signal adds nothing
])
def test_the_metadata_verdict_is_a_weighted_vote(api, run_job, verdict, expected, label):
    aigc = plain("ai_generated", 2)
    swap = plain("deepfake", 1)
    job = run_job({aigc[0]: 0.2, aigc[1]: 0.3, swap[0]: 0.1, "metadata": metadata(verdict)})
    result = analyses(api, job)
    assert result["ai_generated"]["fake_probability"] == pytest.approx(expected)
    assert result["face_swap"]["fake_probability"] == pytest.approx(0.1)  # unaffected
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    assert detail["verdict_label"] == label
    codes = {r["code"] for r in detail["verdict_reasons"]}
    assert ("metadata_ai_indicator" in codes) is (verdict != "unknown")


def test_damaged_or_altered_metadata_does_not_count(api, run_job):
    aigc = plain("ai_generated", 1)
    job = run_job({aigc[0]: 0.2, "metadata": metadata("confirmed", ["C2PA manifest failed validation"])})
    assert analyses(api, job)["ai_generated"]["fake_probability"] == pytest.approx(0.2)
    assert api.get(f"/api/v1/jobs/{job.pk}").json()["verdict"] == "real"


def test_the_weight_is_set_by_the_admin_and_zero_turns_it_off(api, run_job, platform):
    aigc = plain("ai_generated", 1)
    platform.exief_weight = 1
    platform.save()
    job = run_job({aigc[0]: 0.2, "metadata": metadata("confirmed")})
    assert analyses(api, job)["ai_generated"]["fake_probability"] == pytest.approx(0.6)
    platform.exief_weight = 0
    platform.save()
    job = run_job({aigc[0]: 0.2, "metadata": metadata("confirmed")})
    assert analyses(api, job)["ai_generated"]["fake_probability"] == pytest.approx(0.2)


def test_a_declaration_forms_the_ai_generation_analysis_when_no_such_detector_ran(api, run_job):
    swap = plain("deepfake", 1)
    job = run_job({swap[0]: 0.1, "metadata": metadata("confirmed")})
    result = analyses(api, job)
    assert result["ai_generated"]["fake_probability"] == pytest.approx(1.0)
    detail = api.get(f"/api/v1/jobs/{job.pk}").json()
    assert (detail["verdict"], detail["ai_generated"]) == ("fake", True)


def test_admins_set_the_weight_on_detection_setup(api, client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    assert api.patch("/api/v1/admin/models/setup", {"exief_weight": 2}, format="json").status_code == 403
    res = admin.patch("/api/v1/admin/models/setup", {"exief_weight": 2}, format="json")
    assert res.status_code == 200 and res.json()["exief_weight"] == 2
    assert admin.patch("/api/v1/admin/models/setup", {"exief_weight": -1}, format="json").status_code == 400


def test_admins_see_what_exief_found_and_its_measured_accuracy(api, run_job, client_for, make_user):
    admin = client_for(make_user(roles=("admin",)), mfa=True)
    aigc = plain("ai_generated", 1)
    declared = run_job({aigc[0]: 0.2, "metadata": metadata("confirmed")})
    stripped = run_job({aigc[0]: 0.7, "metadata": metadata("unknown")})  # an AI image without provenance
    camera = run_job({aigc[0]: 0.1, "metadata": metadata("unknown")})
    altered = run_job({aigc[0]: 0.1, "metadata": metadata("confirmed", ["C2PA manifest failed validation"])})
    for job, truth in ((declared, "ai_generated"), (stripped, "ai_generated"), (camera, "authentic"),
                       (altered, "authentic")):
        assert admin.put(f"/api/v1/admin/jobs/{job.pk}/truth", {"truth": truth}, format="json").status_code == 200
    block = admin.get(f"/api/v1/admin/jobs/{declared.pk}/detectors").json()["exief"]
    assert (block["verdict"], block["counted"], block["fake_probability"], block["weight"]) == (
        "confirmed", True, 1.0, 3.0)
    assert block["signals"][0]["id"] == "c2pa_trained"
    # It flags only the declared file: right on 3 of 4 (the stripped AI image is missed), never wrong
    # about an authentic one - the altered file's claim was not trusted.
    assert block["measured"] | {"auc": None} == {
        "files": 4, "fake_files": 2, "authentic_files": 2, "accuracy": 0.75, "precision": 1.0, "recall": 0.5,
        "specificity": 1.0, "auc": None}
    altered_block = admin.get(f"/api/v1/admin/jobs/{altered.pk}/detectors").json()["exief"]
    assert (altered_block["counted"], altered_block["untrustworthy"]) == (False, ["C2PA manifest failed validation"])
    setup = admin.get("/api/v1/admin/models/setup").json()
    assert setup["exief_weight"] == 3.0 and setup["exief_measured"]["files"] == 4
    assert api.get(f"/api/v1/admin/jobs/{declared.pk}/detectors").status_code == 403
