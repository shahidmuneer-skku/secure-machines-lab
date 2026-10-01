"""WebSocket service for long-form video: the browser streams the file, results stream back live.

Protocol on /stream/ws (JSON text frames unless noted):

    client → {"action": "auth", "token": "..."}              token from POST /api/v1/long-video/sessions
    server ← {"type": "ready", "chunk_size": ..., "size": ...}
    client → binary frames with the file's bytes, then {"action": "upload_done"}
    server ← {"type": "uploaded", "bytes": n}                after every chunk (progress + flow control)
    server ← {"type": "queued", "position": n}               while another scan holds the GPU
    server ← {"type": "meta" | "interval" | "done" ...}      the legacy engine's events, live
    client → {"action": "stop"}                              any time; analysed minutes are still charged
    server ← {"type": "finished", "status": "done|stopped|error", "job_id": ..., "credits_charged": n}

The file lives in STREAM_WORK_DIR only while the socket is open and is deleted afterwards; it
never reaches media storage. Everything that was paid for (model, range, size) comes from the
signed token, not from the client.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from . import engines, settings
from .reporter import ApiRefused, claim, report
from .tokens import TokenError, verify

logger = logging.getLogger("sml_stream")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.WORK_DIR.mkdir(parents=True, exist_ok=True)
    if settings.PRELOAD_MODEL:
        # Load SKKU-AIGC once, in the background, so the first scan does not pay for it.
        asyncio.get_running_loop().run_in_executor(None, engines.builtin_engine)
    yield


app = FastAPI(title="SML long-form stream", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)

_gpu = asyncio.Lock()
_waiting = 0
REPORT_EVERY = 2.0  # seconds between interval batches sent to the API


class _Stopped(Exception):
    """The client stopped the scan (or went away) before it finished."""


# Engine events go to the browser with these fields only: the legacy engines also report model
# names, checkpoints and devices, which users must not see.
PUBLIC_EVENT_FIELDS = {
    "meta": ("type", "duration_sec", "start_sec", "end_sec", "interval_sec", "num_intervals"),
    "interval": ("type", "index", "start_sec", "end_sec", "fake_probability"),
    "done": ("type", "average_fake_probability", "verdict"),
}


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    fields = PUBLIC_EVENT_FIELDS.get(str(event.get("type")), ("type",))
    return {k: event[k] for k in fields if k in event}


def _action(msg: dict[str, Any]) -> str:
    try:
        return str(json.loads(msg.get("text") or "{}").get("action", ""))
    except (ValueError, AttributeError):
        return ""


_gpu_stats_cache: tuple[float, dict[str, Any] | None] = (0.0, None)


def _gpu_stats() -> dict[str, Any] | None:
    """Name and memory of the service's GPU (nvidia-smi, PCI bus order like CUDA_VISIBLE_DEVICES)."""
    global _gpu_stats_cache
    if time.monotonic() - _gpu_stats_cache[0] < 5:
        return _gpu_stats_cache[1]
    stats = None
    index = os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")[0].strip()
    smi = shutil.which("nvidia-smi")
    if smi and index.isdigit():
        with contextlib.suppress(OSError, subprocess.SubprocessError, ValueError, IndexError):
            # Fixed arguments; the index is validated as digits above.
            out = subprocess.run([smi, "-i", index, "--format=csv,noheader,nounits",  # noqa: S603
                                  "--query-gpu=name,memory.used,memory.total,utilization.gpu"],
                                 capture_output=True, text=True, timeout=5, check=True).stdout
            name, used, total, util = [c.strip() for c in out.strip().splitlines()[0].split(",")]
            stats = {"index": index, "name": name, "mem_used_mb": int(float(used)),
                     "mem_total_mb": int(float(total)), "util": int(float(util))}
    _gpu_stats_cache = (time.monotonic(), stats)
    return stats


@app.get("/stream/health")
async def health() -> JSONResponse:
    gpu = await asyncio.get_running_loop().run_in_executor(None, _gpu_stats)
    return JSONResponse({"status": "ok", "busy": _gpu.locked(), "waiting": _waiting,
                         "model_loaded": engines._builtin is not None, "gpu": gpu})


@app.get("/stream/models")
async def models() -> JSONResponse:
    loop = asyncio.get_running_loop()
    return JSONResponse({"models": await loop.run_in_executor(None, engines.catalog)})


def _probe(path: Path) -> dict[str, Any]:
    import av  # PyAV ships with the legacy environment

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        duration = float(container.duration / 1e6) if container.duration else 0.0
        if not duration and stream.duration and stream.time_base:
            duration = float(stream.duration * stream.time_base)
        return {"duration": duration, "width": stream.codec_context.width, "height": stream.codec_context.height,
                "fps": float(stream.average_rate or 0)}


def _preview(path: Path, at: float) -> str:
    """Small JPEG (base64) of one frame, used as the job's thumbnail in history."""
    import av

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        if stream.time_base:
            container.seek(int(max(0.0, at) / stream.time_base), stream=stream)
        for frame in container.decode(video=0):
            image = frame.to_image()
            image.thumbnail((480, 480))
            buf = io.BytesIO()
            image.convert("RGB").save(buf, "JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode()
    return ""


async def _send(ws: WebSocket, message: dict[str, Any]) -> None:
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):
        await ws.send_json(message)


async def _fail(ws: WebSocket, message: str, code: int = 4400) -> None:
    await _send(ws, {"type": "error", "message": message})
    with contextlib.suppress(RuntimeError):
        await ws.close(code=code)


@app.websocket("/stream/ws")
async def stream(ws: WebSocket) -> None:
    global _waiting
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=20)
        claims = verify(str(first.get("token", "")), settings.SHARED_SECRET) if first.get("action") == "auth" else None
    except TokenError as exc:
        return await _fail(ws, str(exc), 4401)
    except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        return await _fail(ws, "Authenticate first.", 4401)
    if not claims:
        return await _fail(ws, "Authenticate first.", 4401)

    sid = str(claims["sid"])
    loop = asyncio.get_running_loop()
    try:
        # The token only names the session; what was paid for comes from the API, once.
        claims = await loop.run_in_executor(None, claim, sid)
    except ApiRefused:
        return await _fail(ws, "This scan was already started or canceled. Start a new scan.", 4409)
    except ConnectionError:
        return await _fail(ws, "The scan could not be started. Please try again.")

    engine = await loop.run_in_executor(None, engines.resolve, str(claims["model"]))
    if engine is None:
        logger.error("Stream %s: detector %s is not available", sid, claims["model"])
        return await _fail(ws, "Long-form scanning is not available right now.")

    size = int(claims["size"])
    suffix = re.sub(r"[^a-z0-9.]", "", Path(str(claims.get("name", ""))).suffix.lower())[:8] or ".mp4"
    path = settings.WORK_DIR / f"{sid}{suffix}"
    stop = threading.Event()
    state: dict[str, Any] = {"intervals": [], "summary_statistic": "mean", "frames_scored": 0, "frames_voted_fake": 0}
    status, error = "error", ""

    try:
        # --- 1. receive the file -----------------------------------------------------------
        await _send(ws, {"type": "ready", "chunk_size": settings.CHUNK_BYTES, "size": size})
        received = 0
        with path.open("wb") as out:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    raise _Stopped
                if msg.get("bytes") is not None:
                    chunk = msg["bytes"]
                    received += len(chunk)
                    if received > size:
                        error = "The file is larger than the scan that was paid for."
                        return await _fail(ws, error)
                    await loop.run_in_executor(None, out.write, chunk)
                    await _send(ws, {"type": "uploaded", "bytes": received})
                    continue
                action = _action(msg)
                if action == "upload_done":
                    break
                if action == "stop":
                    raise _Stopped
        if received != size:
            error = f"Upload incomplete ({received} of {size} bytes)."
            return await _fail(ws, error)

        # --- 2. probe, clamp the range to what was paid for, report the start ------------------
        try:
            info = await loop.run_in_executor(None, _probe, path)
        except Exception as exc:  # noqa: BLE001 - any decoder error means an unreadable video
            error = f"The video could not be decoded: {exc}"[:300]
            return await _fail(ws, "The video could not be decoded.")
        duration = info["duration"]
        start = float(claims.get("start") or 0.0)
        requested_end = claims.get("end")
        end = min(duration, float(requested_end) if requested_end is not None else duration,
                  start + float(claims["max_seconds"]) + settings.RANGE_TOLERANCE)
        if duration <= 0 or start >= end:
            error = "The selected range is outside the video."
            return await _fail(ws, error)
        preview = await loop.run_in_executor(None, _preview, path, start + (end - start) / 2)
        try:
            await loop.run_in_executor(None, lambda: report(sid, "started", {
                **info, "start_sec": start, "end_sec": end, "preview_jpeg": preview}))
        except ApiRefused:
            error = "This scan is no longer valid (canceled or expired)."
            return await _fail(ws, error, 4409)

        # --- 3. wait for the GPU -----------------------------------------------------------------
        _waiting += 1
        try:
            while _gpu.locked():
                await _send(ws, {"type": "queued", "position": _waiting})
                await asyncio.sleep(2)
            await _gpu.acquire()
        finally:
            _waiting -= 1

        # --- 4. analyse, streaming events ------------------------------------------------------
        try:
            queue: asyncio.Queue = asyncio.Queue(maxsize=64)
            done_marker = object()
            face_crop = engines.face_crop_for(engine, claims.get("face_crop"))

            def producer() -> None:
                try:
                    for event in engines.run(engine, str(path), interval=float(claims["interval"]), start=start,
                                             end=end, whole=bool(claims.get("whole")), face_crop=face_crop,
                                             should_stop=stop.is_set):
                        asyncio.run_coroutine_threadsafe(queue.put(event), loop).result()
                except Exception as exc:  # noqa: BLE001 - surfaced to the client and the API
                    asyncio.run_coroutine_threadsafe(queue.put({"_error": str(exc)}), loop).result()
                finally:
                    asyncio.run_coroutine_threadsafe(queue.put(done_marker), loop)

            async def listen() -> None:
                try:
                    while True:
                        msg = await ws.receive()
                        if msg.get("type") == "websocket.disconnect" or _action(msg) == "stop":
                            stop.set()
                            return
                except (WebSocketDisconnect, RuntimeError):
                    stop.set()

            listener = asyncio.create_task(listen())
            worker = loop.run_in_executor(None, producer)
            pending: list[dict[str, Any]] = []
            last_report = time.monotonic()
            status = "done"
            while True:
                event = await queue.get()
                if event is done_marker:
                    break
                if "_error" in event:
                    if "cancel" in event["_error"].lower():
                        status = "stopped"
                    else:
                        status, error = "error", event["_error"][:1000]
                        await _send(ws, {"type": "error", "message": "The analysis failed."})
                    continue
                kind = event.get("type")
                if kind == "meta":
                    state["summary_statistic"] = event.get("summary_statistic") or "mean"
                    state["num_intervals"] = event.get("num_intervals")
                elif kind == "interval":
                    row = {"index": event.get("index"), "start_sec": event.get("start_sec"),
                           "end_sec": event.get("end_sec"), "frames_used": event.get("frames_used"),
                           "fake_probability": float(event.get("fake_probability") or 0.0)}
                    state["intervals"].append(row)
                    state["frames_scored"] += int(event.get("frames_used") or 0)
                    state["frames_voted_fake"] += int(event.get("frames_voted_fake") or 0)
                    pending.append(row)
                elif kind == "done" and event.get("summary_statistic"):
                    state["summary_statistic"] = event["summary_statistic"]
                    state["frames_scored"] = event.get("frames_scored") or state["frames_scored"]
                    state["frames_voted_fake"] = event.get("frames_voted_fake") or state["frames_voted_fake"]
                await _send(ws, _public_event(event))
                if pending and (time.monotonic() - last_report > REPORT_EVERY or kind == "done"):
                    batch, pending = pending, []
                    last_report = time.monotonic()
                    try:
                        await loop.run_in_executor(None, lambda b=batch: report(sid, "intervals", {
                            "intervals": b, "total": state.get("num_intervals")}))
                    except ApiRefused:
                        stop.set()  # canceled from the job page
                    except ConnectionError:
                        logger.warning("Stream %s: interval report failed; the final report carries all", sid)
            await worker
            listener.cancel()
            if stop.is_set() and status == "done":
                status = "stopped"
        finally:
            _gpu.release()
    except (_Stopped, WebSocketDisconnect):
        status = "stopped"
    finally:
        stop.set()
        path.unlink(missing_ok=True)
        # Always settle: the API charges analysed minutes, or releases everything on failure.
        await _finish(ws, sid, status, state, error)


async def _finish(ws: WebSocket, sid: str, status: str, state: dict[str, Any], error: str) -> None:
    intervals = state["intervals"]
    analysed = sum(max(0.0, float(i["end_sec"] or 0) - float(i["start_sec"] or 0)) for i in intervals)
    payload = {"status": status, "analysed_seconds": round(analysed, 3), "intervals": intervals,
               "average": round(engines.summary(state), 6), "summary_statistic": state["summary_statistic"],
               "error": error}
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: report(sid, "finished", payload, retries=5))
    except (ApiRefused, ConnectionError) as exc:
        logger.error("Stream %s: final report failed: %s", sid, exc)
        result = {}
    await _send(ws, {"type": "finished", "status": status, "analysed_seconds": payload["analysed_seconds"],
                     "average": payload["average"], **{k: result.get(k) for k in ("job_id", "credits_charged",
                                                                                   "verdict")}})
    with contextlib.suppress(RuntimeError):
        await ws.close()
