"""Deterministic stand-in for real models (used until the conda envs are installed, and in tests).

Scores are derived from the file hash and model id, so re-runs agree. Every
result carries `simulated: true`, which the UI shows as a "Simulated" badge.
"""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from ..context import TaskContext
from .base import ModelResult

STAGES = ["Loading model weights", "Preprocessing", "Detecting faces", "Running inference", "Aggregating scores"]


def _unit(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class SimulatedAdapter:
    def __init__(self, model: dict[str, Any], speed: float = 1.0):
        self.id = model["id"]
        self.model = model
        self.speed = speed

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        sha = (ctx.envelope.get("media") or {}).get("sha256") or hashlib.sha256(media_path.read_bytes()).hexdigest()
        ctx.log(f"[simulated] {self.id} on {media_type} (real model env not installed)")
        duration = (4 if media_type == "image" else 10) * self.speed
        steps = 20
        for i in range(steps):
            stage = STAGES[min(len(STAGES) - 1, i * len(STAGES) // steps)]
            ctx.progress(5 + 90 * i / steps, stage)
            if i % 5 == 0:
                ctx.log(stage)
            time.sleep(duration / steps)

        if self.model.get("face_required") and _unit(sha, "face") < 0.08:
            ctx.log("No face found in the media")
            return ModelResult(no_face=True, simulated=True)

        base = _unit(sha, "base")
        noise = (_unit(sha, self.id) - 0.5) * 0.3
        prob = min(0.99, max(0.01, 0.15 + 0.7 * base + noise))
        per_frame: list[dict[str, Any]] = []
        if media_type == "video":
            frames = 40
            for f in range(frames):
                wobble = 0.12 * math.sin(f / 4 + base * 6)
                per_frame.append({"frame": str(f * 5), "fake_prob": round(min(1, max(0, prob + wobble)), 4)})
        elif self.model.get("xai", "none") != "none":
            heat = _heatmap(media_path, sha + self.id, ctx.workdir / f"{self.id}_xai.png")
            if heat is not None:
                ctx.add_artifact(heat, kind="xai", label=f"{self.model.get('xai', 'xai').title()} (simulated)")
        ctx.progress(97, "Finalizing", force=True)
        return ModelResult(fake_prob=round(prob, 6), per_frame=per_frame, simulated=True)


def _heatmap(media_path: Path, seed: str, out: Path) -> Path | None:
    try:
        with Image.open(media_path) as img:
            base = img.convert("RGB")
        base.thumbnail((768, 768))
        w, h = base.size
        overlay = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(overlay)
        cx, cy = int(w * (0.3 + 0.4 * _unit(seed, "x"))), int(h * (0.3 + 0.4 * _unit(seed, "y")))
        radius = int(min(w, h) * (0.18 + 0.12 * _unit(seed, "r")))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius // 2 or 1))
        heat = Image.merge("RGB", (overlay, overlay.point(lambda v: v // 3), Image.new("L", (w, h), 0)))
        gray = base.convert("L").convert("RGB")
        blended = Image.blend(gray, heat, 0.55)
        out.parent.mkdir(parents=True, exist_ok=True)
        blended.save(out, "PNG")
        return out
    except Exception:  # noqa: BLE001
        return None
