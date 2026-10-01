"""The service is tested with a fake engine; the legacy models and GPUs are not needed."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

os.environ["STREAM_SHARED_SECRET"] = "test-stream-secret"
os.environ["API_INTERNAL_URL"] = "http://api.test"
os.environ["STREAM_PRELOAD_MODEL"] = "0"

# Sessions "paid for" through the API in a test: session id → what the claim endpoint returns.
PAID: dict[str, dict[str, Any]] = {}


def make_video(path: Path, seconds: int = 4, fps: int = 10) -> Path:
    import av
    import numpy as np

    with av.open(str(path), "w") as out:
        stream = out.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(seconds * fps):
            frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i % 255, dtype=np.uint8), format="rgb24")
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


class FakeEngine:
    face_crop_support = "optional"
    face_crop_default = False

    def __init__(self, interval_prob: float = 0.8, fail: bool = False):
        self.interval_prob, self.fail = interval_prob, fail


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    from sml_stream import app as app_module
    from sml_stream import engines, settings

    monkeypatch.setattr(settings, "WORK_DIR", tmp_path / "work")
    (tmp_path / "work").mkdir()
    reports: list[tuple[str, str, dict[str, Any]]] = []
    engine = FakeEngine()

    def fake_report(session_id: str, event: str, payload: dict[str, Any], **kw: Any) -> dict[str, Any]:
        reports.append((session_id, event, payload))
        return {"job_id": "job-1", "credits_charged": 4, "verdict": "fake"} if event == "finished" else {"ok": True}

    def fake_run(engine_, path, *, interval, start, end, whole, face_crop, should_stop):  # type: ignore[no-untyped-def]
        import time

        count = max(1, int((end - start) // interval))
        yield {"type": "meta", "num_intervals": count, "summary_statistic": "mean", "model": "SKKU-AIGC",
               "checkpoint": "/home/ops/videoCheckpoint.pt", "device": "cuda:0"}
        for i in range(count):
            if should_stop():
                raise RuntimeError("Processing cancelled by user")
            if engine_.fail and i == 1:
                raise RuntimeError("CUDA error at /home/ops/secret/model.py")
            time.sleep(0.02)
            yield {"type": "interval", "index": i, "start_sec": start + i * interval,
                   "end_sec": start + (i + 1) * interval, "fake_probability": engine_.interval_prob, "frames_used": 8}
        yield {"type": "done", "average_fake_probability": engine_.interval_prob}

    def fake_claim(session_id: str) -> dict[str, Any]:
        """The API hands out a session's paid parameters once (see the Django claim endpoint)."""
        from sml_stream.reporter import ApiRefused

        if session_id not in PAID:
            raise ApiRefused("already claimed")
        return PAID.pop(session_id)

    PAID.clear()
    monkeypatch.setattr(app_module, "report", fake_report)
    monkeypatch.setattr(app_module, "claim", fake_claim)
    monkeypatch.setattr(engines, "resolve", lambda model_id: engine if model_id == "skku-aigc" else None)
    monkeypatch.setattr(engines, "run", fake_run)
    return {"reports": reports, "engine": engine, "tmp": tmp_path}
