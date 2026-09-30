"""The WebSocket protocol end to end with a fake engine."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sml_stream import app as app_module
from sml_stream.tokens import sign

from .conftest import make_video


def token(size: int, **claims) -> str:  # type: ignore[no-untyped-def]
    base = {"sid": "sess-1", "uid": "u", "model": "skku-aigc", "name": "clip.mp4", "size": size, "start": 0.0,
            "end": None, "max_seconds": 4.0, "interval": 1.0, "whole": False, "face_crop": None,
            "exp": time.time() + 60}
    return sign({**base, **claims}, "test-stream-secret")


def upload(ws, data: bytes, chunk: int = 1000) -> None:  # type: ignore[no-untyped-def]
    for i in range(0, len(data), chunk):
        ws.send_bytes(data[i:i + chunk])
        assert ws.receive_json()["type"] == "uploaded"
    ws.send_json({"action": "upload_done"})


def events_until_finished(ws) -> list[dict]:  # type: ignore[no-untyped-def]
    out = []
    while True:
        msg = ws.receive_json()
        out.append(msg)
        if msg["type"] == "finished":
            return out


def test_full_scan_streams_intervals_and_reports_settlement(service):
    data = make_video(service["tmp"] / "v.mp4").read_bytes()
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json({"action": "auth", "token": token(len(data))})
        assert ws.receive_json()["type"] == "ready"
        upload(ws, data)
        events = events_until_finished(ws)
    types = [e["type"] for e in events]
    assert types[0] == "meta" and types.count("interval") == 4 and "done" in types
    assert events[-1] == {"type": "finished", "status": "done", "analysed_seconds": 4.0, "average": 0.8,
                          "job_id": "job-1", "credits_charged": 4, "verdict": "fake"}
    reported = [event for _, event, _ in service["reports"]]
    assert reported[0] == "started" and reported[-1] == "finished" and "intervals" in reported
    started = service["reports"][0][2]
    assert started["duration"] == pytest.approx(4.0, abs=0.2) and started["preview_jpeg"]
    assert not list((service["tmp"] / "work").iterdir()), "the video is deleted after the scan"


def test_range_is_clamped_to_what_was_paid_for(service):
    data = make_video(service["tmp"] / "v.mp4").read_bytes()
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json({"action": "auth", "token": token(len(data), max_seconds=2.0, end=None)})
        ws.receive_json()
        upload(ws, data)
        events = events_until_finished(ws)
    assert [e for e in events if e["type"] == "interval"][-1]["end_sec"] <= 2.0 + 1.0
    assert service["reports"][0][2]["end_sec"] == pytest.approx(3.0)


def test_stop_during_analysis_is_charged_for_what_ran(service):
    data = make_video(service["tmp"] / "v.mp4", seconds=8).read_bytes()
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json({"action": "auth", "token": token(len(data), max_seconds=8.0)})
        ws.receive_json()
        upload(ws, data)
        while ws.receive_json()["type"] != "interval":
            pass
        ws.send_json({"action": "stop"})
        events = events_until_finished(ws)
    assert events[-1]["status"] == "stopped"
    assert 1.0 <= events[-1]["analysed_seconds"] < 8.0


def test_engine_errors_are_generic_for_the_user(service):
    service["engine"].fail = True
    data = make_video(service["tmp"] / "v.mp4").read_bytes()
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json({"action": "auth", "token": token(len(data))})
        ws.receive_json()
        upload(ws, data)
        events = events_until_finished(ws)
    assert all("/home/ops" not in str(e) for e in events)
    final = service["reports"][-1][2]
    assert final["status"] == "error" and "/home/ops" in final["error"]  # staff-only detail


@pytest.mark.parametrize(("first", "code"), [({"action": "auth", "token": "bad"}, 4401), ({"action": "hello"}, 4401)])
def test_unauthenticated_sockets_are_closed(service, first, code):
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json(first)
        assert ws.receive_json()["type"] == "error"
    assert not service["reports"]


def test_a_token_starts_only_one_scan(service):
    data = make_video(service["tmp"] / "v.mp4").read_bytes()
    t = token(len(data))
    with TestClient(app_module.app) as client:
        with client.websocket_connect("/stream/ws") as ws:
            ws.send_json({"action": "auth", "token": t})
            ws.receive_json()
            upload(ws, data)
            events_until_finished(ws)
        with client.websocket_connect("/stream/ws") as ws:
            ws.send_json({"action": "auth", "token": t})
            assert "already" in ws.receive_json()["message"]


def test_uploads_larger_than_paid_are_refused(service):
    data = make_video(service["tmp"] / "v.mp4").read_bytes()
    with TestClient(app_module.app) as client, client.websocket_connect("/stream/ws") as ws:
        ws.send_json({"action": "auth", "token": token(len(data) - 10)})
        ws.receive_json()
        ws.send_bytes(data)
        messages = []
        with pytest.raises(WebSocketDisconnect):  # the server closes after the error and the final report
            while True:
                messages.append(ws.receive_json())
    assert any(m.get("type") == "error" and "larger" in m.get("message", "") for m in messages)
    assert service["reports"][-1][2]["status"] == "error"
