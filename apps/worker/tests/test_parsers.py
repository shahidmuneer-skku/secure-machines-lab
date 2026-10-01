"""Score parsers must understand every legacy model's stdout format."""

from __future__ import annotations

from pathlib import Path

import pytest

from sml_worker.adapters import parsers


@pytest.mark.parametrize(("stdout", "expected"), [
    ("loading...\nFake Prob: 0.83\n", 0.83),
    ("Fake Prob: 83.0\n", 0.83),
    ("Aggregated FAKE Prob: 0.25", 0.25),
    ("real: 0.2 fake: 0.8\nreal: 0.9 fake: 0.1\n", 0.1),  # the last pair wins
    ("real: 30 fake: 90", 0.75),  # renormalized when they do not add up to 100
    ("nothing useful", None),
])
def test_standard(stdout, expected):
    result = parsers.parse_standard(stdout)
    assert result == pytest.approx(expected) if expected is not None else result is None


def test_b2_handles_tensor_repr():
    out = "Average Real Probability: tensor(0.1000)\nAverage Fake Probability: tensor(0.9000)"
    assert parsers.parse_b2(out) == pytest.approx(0.9)


def test_center_prints_percentages():
    assert parsers.parse_center("real: 12.5\nfake: 87.5") == pytest.approx(0.875)
    assert parsers.parse_center("real: 0.4 fake: 0.6") == pytest.approx(0.6)


def test_safe_csv_prefers_the_result_file(tmp_path: Path):
    f = tmp_path / "result.csv"
    f.write_text("image,prediction\nx.png,0.7\n")
    assert parsers.parse_safe_csv("prediction: 0.1", f) == pytest.approx(0.7)
    assert parsers.parse_safe_csv("prediction: 0.1", tmp_path / "missing.csv") == pytest.approx(0.1)


def test_faces_and_no_face_markers():
    assert parsers.parse_faces('FACES_JSON:{"faces": [{"x": 1}, "junk"]}') == [{"x": 1}]
    assert parsers.parse_faces("FACES_JSON:{broken") == []
    assert parsers.detect_no_face("", "RuntimeError: No faces detected in image")
    assert parsers.detect_no_face("얼굴을 찾지 못했습니다", "")
    assert not parsers.detect_no_face("ok", "")


def test_frame_csv_progress_and_total(tmp_path: Path):
    f = tmp_path / "x.csv"
    f.write_text("frame,real,fake,extra,progress\n1,0.9,0.1,,10\n2,0.2,0.8,,20\nTotal,0.4,0.6,,100\n")
    rows, progress, total = parsers.read_frame_csv(f)
    assert [r["fake_prob"] for r in rows] == [0.1, 0.8]
    assert progress == 100.0
    assert total == pytest.approx(0.6)
    assert parsers.read_frame_csv(tmp_path / "none.csv") == ([], None, None)


def test_frame_csv_without_any_face_has_no_total(tmp_path: Path):
    """BEYBI and XB-DFD end with "Total result,0,0,no_face,100" when no frame had a face."""
    f = tmp_path / "x.csv"
    f.write_text("frame,real,fake,result,progress\n0,0.5,0.5,processing,0.0\n0,,,no_face,50.00\n1,,,no_face,100.00\n"
                 "Total result,0,0,no_face,100\n")
    rows, progress, total = parsers.read_frame_csv(f)
    assert (rows, total, progress) == ([], None, 100.0)  # the "processing" placeholder is not a frame


def test_frame_csv_skips_frames_without_a_face(tmp_path: Path):
    f = tmp_path / "x.csv"  # XB-DFD: frames without a face have no score
    f.write_text("frame,real,fake,result,progress\n0,0.5,0.5,processing,0.0\n0,0.7000,0.3000,real,33.33\n"
                 "1,,,no_face,66.67\n2,0.2000,0.8000,fake,100.00\nTotal result,0.4500,0.5500,fake,100\n")
    rows, _, total = parsers.read_frame_csv(f)
    assert [(r["frame"], r["fake_prob"]) for r in rows] == [("0", 0.3), ("2", 0.8)]
    assert total == pytest.approx(0.55)


def test_missing_anti_spoofing_code_is_a_failure_not_a_result():
    from sml_worker.adapters.audit import _raise_if_fas_unavailable
    from sml_worker.adapters.base import AdapterError

    broken = {"success": True, "fas_results": [{"label": "ERROR", "error": "CVPR24-FAS directory not found"}]}
    with pytest.raises(AdapterError) as err:
        _raise_if_fas_unavailable(broken)
    assert err.value.code == "CONFIG_ERROR"
    _raise_if_fas_unavailable({"fas_results": [{"label": "REAL"}, {"label": "ERROR"}]})  # partial result is kept
    _raise_if_fas_unavailable({"fas_results": []})


def test_prompts_never_name_detectors():
    from sml_worker.agents.explain import build_prompt as explain_prompt
    from sml_worker.agents.news import build_prompt as news_prompt

    context = {"verdict": "fake", "fake_probability": 0.9, "media_type": "image",
               "provenance": {"ai_generated": True, "evidence": [{"source": "C2PA", "detail": "AI"}]},
               "checks": [{"id": "face", "status": "done", "result": {"faces_found": True}}],
               "summary": {"models": [{"name": "Xception", "fake_prob": 0.9}]}}
    text = explain_prompt(context, "media.png", ["heatmap_1.png"], "en")
    assert "Xception" not in text and "How the detectors agree" not in text and "Confidential" in text
    news = news_prompt({"title": "x"}, [("a.png", "image")], [{"file": "a.png", "analyses": [
        {"analysis": "face_swap", "status": "no_face", "fake_prob": None},
        {"analysis": "ai_generated", "status": "done", "fake_prob": 0.8}]}], "en")
    assert "skku" not in news.lower()
    assert "face-swap analysis: no face found; AI-generation analysis: fake probability 80.0%" in news
    text = explain_prompt({**context, "analyses": [{"id": "face_swap", "verdict": "fake", "fake_probability": 0.9,
                                                    "status": "done"}]}, "media.png", [], "en")
    assert '"analysis": "face-swap analysis"' in text and "Results by analysis" in text


def test_beybi_frame_csv_percents_and_frame_counts(tmp_path: Path):
    """BEYBI writes per-frame percents ("73%") and a total row of frame counts (job 01a0f649)."""
    f = tmp_path / "x.csv"
    f.write_text("frame,real,fake,result,progress\n0,0.5,0.5,processing,0.0\n0,73%,27%,real,0.00\n"
                 "1,1%,99%,fake,50.00\n\nTotal result,145,0,real,100\n")
    rows, progress, total = parsers.read_frame_csv(f)
    assert [(r["frame"], r["fake_prob"]) for r in rows] == [("0", 0.27), ("1", 0.99)]
    assert (total, progress) == (0.0, 100.0)
    f.write_text("frame,real,fake,result,progress\nTotal result,30,120,fake,100\n")
    assert parsers.read_frame_csv(f)[2] == pytest.approx(0.8)  # share of fake frames, not 100 - 30
    f.write_text("frame,real,fake,result,progress\nTotal result,30,20,real,100\n")
    assert parsers.read_frame_csv(f)[2] == pytest.approx(0.4)
    assert parsers.to_percent("1%") == 1.0 and parsers.to_percent("0.5") == 50.0 and parsers.to_percent("x%") is None
