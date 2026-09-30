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
