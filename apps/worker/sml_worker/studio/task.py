"""Runs one studio job: prompt check → reference checks → generation on the studio server → upload.

Outputs are stored as the user's own media (`media/u/<user>/<id>.png` plus a thumbnail), so they can
be downloaded, edited again or analysed; the API registers them when the job finishes. Failures are
classified (PROMPT_BLOCKED, INPUT_BLOCKED, CONSENT_REQUIRED, OUTPUT_BLOCKED, ...) and the job is
not charged for them.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from ..adapters.base import AdapterError, ModelResult
from ..clients import download, upload
from ..context import TaskContext
from . import client, studio_config
from .safety import SafetyUnavailable, check_prompt

logger = logging.getLogger(__name__)

THUMB_SIDE = 640


def run_studio(envelope: dict[str, Any], ctx: TaskContext) -> ModelResult:
    req = envelope.get("studio") or {}
    model_id, mode = req.get("model", ""), req.get("mode", "generate")
    prompt, negative = str(req.get("prompt") or ""), str(req.get("negative_prompt") or "")
    ctx.log(f"Studio {mode} with {model_id}")

    ctx.progress(1, "Checking the request", force=True)
    try:
        verdict = check_prompt(prompt, negative, req.get("safety_model") or "qwen3.6:27b")
    except SafetyUnavailable as exc:
        raise AdapterError("SAFETY_UNAVAILABLE", str(exc)) from exc
    if not verdict.allowed:
        raise AdapterError("PROMPT_BLOCKED", f"{verdict.category}: {verdict.reason}")
    ctx.check_canceled()

    refs = []
    for index, ref in enumerate(req.get("references") or []):
        refs.append(download(ref["storage_key"], ctx.workdir / f"reference_{index + 1}.{ref.get('extension', 'png')}"))
    faces = 0
    if refs:
        ctx.progress(4, "Checking the reference images", force=True)
        checks = _server({"op": "check", "images": [str(p) for p in refs]}, ctx, timeout=300).get("checks") or []
        threshold = float((studio_config().get("safety") or {}).get("nsfw_threshold", 0.5))
        if any(float(c.get("nsfw", 0)) >= threshold for c in checks):
            raise AdapterError("INPUT_BLOCKED", f"Reference image refused by the safety filter: {checks}")
        faces = sum(int(c.get("faces", 0)) for c in checks)
        if faces and not req.get("consent"):
            raise AdapterError("CONSENT_REQUIRED", f"{faces} face(s) in the reference images and no consent given.")
        if faces:
            ctx.log(f"{faces} face(s) in the reference images; the user confirmed consent")

    ctx.progress(8, "Starting", force=True)
    out_dir = ctx.workdir / "outputs"
    request = {"op": "generate", "model": model_id, "mode": mode, "prompt": prompt, "negative_prompt": negative,
               "images": [str(p) for p in refs], "output_dir": str(out_dir), "count": int(req.get("count") or 1),
               **{k: req.get(k) for k in ("width", "height", "steps", "guidance", "seed", "transparent")}}
    timeout = float((studio_config().get("server") or {}).get("max_request_seconds", 900)) + 600
    done = _server(request, ctx, timeout=timeout).get("done") or {}

    outputs = [_store(Path(o["path"]), o, envelope, ctx) for o in done.get("outputs", [])]
    blocked = int(done.get("blocked", 0))
    if not outputs:
        raise AdapterError("OUTPUT_BLOCKED", f"All {blocked} image(s) were withheld by the safety filter.")
    if blocked:
        ctx.log(f"{blocked} image(s) withheld by the safety filter")
    return ModelResult(extra={"outputs": outputs, "blocked": blocked, "faces": faces, "seed": done.get("seed"),
                              "model": done.get("model", model_id), "peak_gb": done.get("peak_gb")})


def _server(request: dict[str, Any], ctx: TaskContext, *, timeout: float) -> dict[str, Any]:
    def on_event(event: dict[str, Any]) -> None:
        if event.get("event") == "progress":
            images, steps = max(1, int(event.get("images", 1))), max(1, int(event.get("steps", 1)))
            done = int(event.get("image", 0)) + min(1.0, int(event.get("step", 0)) / steps)
            message = f"Generating image {int(event.get('image', 0)) + 1} of {images}" if images > 1 else "Generating"
            ctx.progress(8 + 88 * done / images, message)
        elif event.get("message"):
            ctx.log(str(event["message"]))

    try:
        answer = client.call(request, timeout=timeout, on_event=on_event)
    except client.StudioUnavailable as exc:
        raise AdapterError("STUDIO_UNAVAILABLE", str(exc)) from exc
    except TimeoutError as exc:
        raise AdapterError("TIMEOUT", "The studio server did not answer in time.") from exc
    if "error" in answer:
        error = answer["error"] or {}
        raise AdapterError(str(error.get("code") or "RUNTIME_ERROR"), str(error.get("message") or "")[:500])
    return answer


def _store(path: Path, output: dict[str, Any], envelope: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
    """Upload one output as the user's media, with a thumbnail (transparency shown on white)."""
    media_id = str(uuid.uuid4())
    owner = f"u/{envelope.get('user_id')}"
    data = path.read_bytes()
    key, content_type, size = upload(path, f"media/{owner}/{media_id}.png")
    with Image.open(path) as img:
        frame = img.convert("RGBA")
        canvas = Image.new("RGBA", frame.size, (255, 255, 255, 255))
        canvas.alpha_composite(frame)
        thumb = canvas.convert("RGB")
        thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
        buf = io.BytesIO()
        thumb.save(buf, "JPEG", quality=82, optimize=True)
    thumb_path = ctx.workdir / f"thumb_{media_id}.jpg"
    thumb_path.write_bytes(buf.getvalue())
    thumb_key, _, _ = upload(thumb_path, f"thumbs/{owner}/{media_id}.jpg")
    return {"id": media_id, "storage_key": key, "thumbnail_key": thumb_key, "content_type": content_type,
            "size_bytes": size, "sha256": hashlib.sha256(data).hexdigest(), "width": output.get("width"),
            "height": output.get("height"), "seed": output.get("seed"), "transparent": bool(output.get("transparent"))}
