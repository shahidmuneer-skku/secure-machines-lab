"""What administrators see of each detector (owner, 2026-10-01), and SKKU-P2's authentic boost.

Admins see every detector's answer for a file, its benchmark figures and its accuracy measured on
files they labelled. Users still see only the two analyses (ADR 0011). SKKU-P2 recognises authentic
images best: when it says authentic it counts twice, in both analyses.
"""

from __future__ import annotations

import json

import pytest

from sml.catalog.registry import registry
from sml.jobs.detectors import metrics

pytestmark = pytest.mark.django_db
P2 = "skku-p2"


def plain(family: str, n: int) -> list[str]:
    ids = [m.id for m in registry().enabled_for("image") if m.family == family and not m.fallbacks
           and m.authentic_boost == 1 and not m.authentic_counts_in_all][:n]
    assert len(ids) == n
    return ids


@pytest.fixture
def admin(client_for, make_user):  # type: ignore[no-untyped-def]
    return client_for(make_user(roles=("admin",)), mfa=True)


def analyses(api, job) -> dict[str, dict]:  # type: ignore[no-untyped-def]
    return {a["id"]: a for a in api.get(f"/api/v1/jobs/{job.pk}").json()["analyses"]}


def test_p2_saying_authentic_counts_twice_in_both_analyses(api, run_job):
    swap, aigc = plain("deepfake", 2), plain("ai_generated", 1)
    spec = registry().get(P2)
    assert (spec.authentic_boost, spec.authentic_counts_in_all) == (2.0, True)  # config/models.yaml
    job = run_job({P2: 0.2, swap[0]: 0.7, swap[1]: 0.6, aigc[0]: 0.8})
    result = analyses(api, job)
    assert result["face_swap"]["fake_probability"] == pytest.approx((2 * 0.2 + 0.7 + 0.6) / 4)  # 0.425
    assert result["ai_generated"]["fake_probability"] == pytest.approx((0.8 + 2 * 0.2) / 3)  # 0.4
    assert result["face_swap"]["verdict"] == result["ai_generated"]["verdict"] == "real"
    assert P2 not in json.dumps(api.get(f"/api/v1/jobs/{job.pk}").json())


def test_p2_saying_fake_counts_once_and_only_for_face_swap(api, run_job):
    swap, aigc = plain("deepfake", 1), plain("ai_generated", 1)
    job = run_job({P2: 0.9, swap[0]: 0.3, aigc[0]: 0.2})
    result = analyses(api, job)
    assert result["face_swap"]["fake_probability"] == pytest.approx(0.6)
    assert result["ai_generated"]["fake_probability"] == pytest.approx(0.2)


def test_p2_alone_does_not_create_an_ai_generation_result(api, run_job):
    job = run_job({P2: 0.1})
    assert list(analyses(api, job)) == ["face_swap"]


def test_admins_see_each_detectors_answer_users_do_not(api, admin, run_job):
    swap, aigc = plain("deepfake", 1), plain("ai_generated", 1)
    job = run_job({P2: 0.2, swap[0]: 0.9, aigc[0]: 0.6})
    assert api.get(f"/api/v1/admin/jobs/{job.pk}/detectors").status_code == 403
    res = admin.get(f"/api/v1/admin/jobs/{job.pk}/detectors")
    assert res.status_code == 200, res.content
    body = res.json()
    rows = {d["id"]: d for d in body["detectors"]}
    assert set(rows) == {P2, swap[0], aigc[0]}
    assert rows[P2]["verdict"] == "real" and rows[P2]["weight"] == 2.0
    assert rows[P2]["counted_in"] == ["face_swap", "ai_generated"]
    assert (rows[swap[0]]["verdict"], rows[swap[0]]["weight"], rows[swap[0]]["counted_in"]) == ("fake", 1.0,
                                                                                                ["face_swap"])
    assert rows[aigc[0]]["analysis"] == "ai_generated" and body["truth"]["truth"] is None
    assert [d["analysis"] for d in body["detectors"]] == ["face_swap", "face_swap", "ai_generated"]


def test_labelled_files_measure_each_detector_on_its_own_analysis(api, admin, run_job):
    swap, aigc = plain("deepfake", 1), plain("ai_generated", 1)
    jobs = {"authentic": run_job({swap[0]: 0.2, aigc[0]: 0.7}),
            "face_swap": run_job({swap[0]: 0.8, aigc[0]: 0.3}),
            "ai_generated": run_job({swap[0]: 0.6, aigc[0]: 0.9})}
    assert api.put(f"/api/v1/admin/jobs/{jobs['authentic'].pk}/truth", {"truth": "authentic"},
                   format="json").status_code == 403
    for truth, job in jobs.items():
        res = admin.put(f"/api/v1/admin/jobs/{job.pk}/truth", {"truth": truth}, format="json")
        assert res.status_code == 200 and res.json()["truth"] == truth
    models = {m["id"]: m for m in admin.get("/api/v1/admin/models").json()}
    # Face swap: authentic (0.2 → real, right) + face swap (0.8 → fake, right); the AI-generated file is
    # not this detector's analysis. AI generation: authentic (0.7 → fake, wrong) + AI-generated (right).
    assert models[swap[0]]["measured"] | {"auc": None} == {
        "files": 2, "fake_files": 1, "authentic_files": 1, "accuracy": 1.0, "precision": 1.0, "recall": 1.0,
        "specificity": 1.0, "auc": None}
    assert models[aigc[0]]["measured"]["accuracy"] == 0.5 and models[aigc[0]]["measured"]["specificity"] == 0.0
    assert "truth" not in api.get(f"/api/v1/jobs/{jobs['authentic'].pk}").json()
    admin.put(f"/api/v1/admin/jobs/{jobs['authentic'].pk}/truth", {"truth": None}, format="json")
    detail = admin.get(f"/api/v1/admin/jobs/{jobs['authentic'].pk}/detectors").json()
    assert detail["truth"] == {"truth": None, "labeled_by": None, "labeled_at": None}


def test_benchmarks_and_authentic_boost_are_edited_on_admin_models(admin):
    model = plain("deepfake", 1)[0]
    res = admin.patch("/api/v1/admin/models", {"model_id": model, "benchmark_accuracy": 0.95, "benchmark_auc": 0.97,
                                               "benchmark_dataset": "Celeb-DF v2", "authentic_boost": 1.5},
                      format="json")
    assert res.status_code == 200, res.content
    row = {m["id"]: m for m in admin.get("/api/v1/admin/models").json()}[model]
    assert row["benchmark"] == {"accuracy": 0.95, "auc": 0.97, "dataset": "Celeb-DF v2"}
    assert (row["authentic_boost"], row["authentic_counts_in_all"]) == (1.5, False)
    for bad in ({"benchmark_accuracy": 95}, {"benchmark_auc": "high"}, {"authentic_boost": 0.5}):
        assert admin.patch("/api/v1/admin/models", {"model_id": model, **bad}, format="json").status_code == 400
    admin.patch("/api/v1/admin/models", {"model_id": model, "authentic_boost": None, "benchmark_accuracy": None},
                format="json")
    row = {m["id"]: m for m in admin.get("/api/v1/admin/models").json()}[model]
    assert row["authentic_boost"] == 1.0 and row["benchmark"]["accuracy"] is None


def test_metrics():
    pairs = [(0.9, True), (0.4, True), (0.3, False), (0.6, False)]
    m = metrics(pairs, 0.5)
    assert (m["accuracy"], m["precision"], m["recall"], m["specificity"]) == (0.5, 0.5, 0.5, 0.5)
    assert m["auc"] == pytest.approx(0.75)
    assert metrics([(0.5, True), (0.5, False)], 0.5)["auc"] == 0.5  # ties count half
    assert metrics([], 0.5)["accuracy"] is None


def test_video_timeline_weighs_p2_like_the_verdict():
    from sml.jobs.models import Job, JobTask
    from sml.jobs.public import timeline

    swap, aigc = plain("deepfake", 1)[0], plain("ai_generated", 1)[0]

    def task(target: str, frames: dict[int, float]) -> JobTask:
        return JobTask(kind=JobTask.Kind.MODEL, target=target, status=JobTask.Status.SUCCEEDED,
                       result={"per_frame": [{"frame": str(f), "fake_prob": p} for f, p in frames.items()]})

    tasks = [task(P2, {0: 0.2, 25: 0.2}), task(swap, {0: 0.8, 25: 0.8}), task(aigc, {0: 0.9})]
    points = {(p["analysis"], p["start_sec"]): p["fake_prob"] for p in timeline(Job(media_type="video"), tasks)}
    assert points == {("face_swap", 0.0): pytest.approx(0.4), ("face_swap", 1.0): pytest.approx(0.4),
                      ("ai_generated", 0.0): pytest.approx((0.9 + 0.4) / 3, abs=1e-4)}  # none at 1s: no own frame
