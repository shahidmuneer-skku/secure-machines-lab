"""Runs an existing model script unchanged (the owner's copied models) as a subprocess.

* argv lists only (shell=False) built from config/models.yaml templates
* the model's own conda env python is called directly (no `conda run`)
* the input is staged as <workdir>/<stem>.<ext> where stem = task id, so every
  legacy output (inference_images/, detected/, inference_csv/) is unique per task
* live progress is read from the legacy inference_csv/<stem>.csv while it runs
* CUDA_VISIBLE_DEVICES comes from the worker (never hardcoded in model code)
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from ..config import config, gpu_env
from ..context import Canceled, TaskContext
from ..procenv import model_env
from . import parsers
from .base import AdapterError, ModelResult

logger = logging.getLogger(__name__)

OUTPUT_DIRS = ("inference_images", "detected", "inference_csv")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
OOM_MARKERS = ("CUDA out of memory", "torch.cuda.OutOfMemoryError", "CUBLAS_STATUS_ALLOC_FAILED")
ARCH_MARKERS = ("no kernel image is available", "not compatible with the current PyTorch installation")


def page_type_for(media_type: str, family: str) -> str:
    """Legacy page_type argument (only affects labels/XAI in some scripts)."""
    kind = "ai" if family == "ai_generated" else "deepfake"
    return f"{kind}-{media_type}"


class SubprocessAdapter:
    def __init__(self, model: dict[str, Any], media_spec: dict[str, Any], timeout: int):
        self.id = model["id"]
        self.model = model
        self.spec = media_spec
        self.timeout = timeout

    # --- helpers --------------------------------------------------------------------

    def python_path(self) -> Path:
        return config().conda_python(self.spec.get("conda_env", ""))

    def available(self) -> bool:
        argv = self.spec.get("argv", [])
        if argv and argv[0] == "{python}":
            return self.python_path().exists()
        # bash wrappers call `conda run -n <env>` internally; they need the env too.
        env = self.spec.get("conda_env")
        return (config().conda_root / "envs" / env).exists() if env else True

    def _stage(self, media_path: Path, ctx: TaskContext) -> tuple[Path, Path]:
        stem = ctx.task_id.replace("-", "")
        input_dir = ctx.workdir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        ext = media_path.suffix.lower()
        staged = input_dir / f"{stem}{ext}"
        shutil.copyfile(media_path, staged)
        if self.spec.get("convert_webp_to_jpg") and ext == ".webp":
            from PIL import Image

            jpg = staged.with_suffix(".jpg")
            with Image.open(staged) as img:
                img.convert("RGB").save(jpg, "JPEG", quality=95)
            staged.unlink()
            staged = jpg
        return staged, input_dir

    def _argv(self, staged: Path, input_dir: Path, media_type: str, ctx: TaskContext) -> list[str]:
        c = config()
        original = (ctx.envelope.get("media") or {}).get("original_name", staged.name)
        values = {
            "python": str(self.python_path()),
            "models_root": str(c.models_root),
            "long_video_root": str(c.long_video_root),
            "input": str(staged),
            "input_dir": str(input_dir),
            "stem": staged.stem,
            "workdir": str(ctx.workdir),
            "media": media_type,
            "page_type": page_type_for(media_type, self.model.get("family", "general")),
            "original_name_b64": base64.b64encode(original.encode()).decode(),
            "interval": str((ctx.envelope.get("options") or {}).get("interval_seconds", 5)),
        }
        argv = []
        for part in self.spec["argv"]:
            try:
                argv.append(str(part).format(**values))
            except (KeyError, IndexError) as exc:
                raise AdapterError("CONFIG_ERROR", f"Bad argv template {part!r}: {exc}") from exc
        return argv

    def _env(self) -> dict[str, str]:
        return model_env(self.spec.get("conda_env"))

    # --- run ----------------------------------------------------------------------------

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        c = config()
        staged, input_dir = self._stage(media_path, ctx)
        argv = self._argv(staged, input_dir, media_type, ctx)
        cwd = Path(str(self.spec.get("cwd", "{models_root}")).format(models_root=c.models_root,
                                                                   long_video_root=c.long_video_root))
        if not cwd.exists():
            raise AdapterError("CONFIG_ERROR", f"Model directory not found: {cwd}")
        stem = staged.stem
        progress_csv = c.models_root / "inference_csv" / f"{stem}.csv"
        ctx.log(f"Starting {self.model.get('display_name', {}).get('en', self.id)} "
                f"({media_type}, env {self.spec.get('conda_env', '-')}, GPU {gpu_env()['CUDA_VISIBLE_DEVICES']})")
        ctx.progress(3, "Loading model weights", force=True)

        stdout_lines: deque[str] = deque(maxlen=4000)
        stderr_lines: deque[str] = deque(maxlen=800)
        proc = subprocess.Popen(
            argv, cwd=str(cwd), env=self._env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", start_new_session=True,
        )

        def pump(stream: Any, sink: deque[str], is_err: bool) -> None:
            for line in stream:
                sink.append(line)
                text = line.strip()
                if not is_err and text and len(text) < 200 and not text.startswith("FACES_JSON"):
                    lowered = text.lower()
                    if any(k in lowered for k in ("load", "detect", "process", "frame", "face", "infer", "done",
                                                  "prob", "extract")):
                        ctx.log(text)

        threads = [threading.Thread(target=pump, args=(proc.stdout, stdout_lines, False), daemon=True),
                   threading.Thread(target=pump, args=(proc.stderr, stderr_lines, True), daemon=True)]
        for t in threads:
            t.start()

        started = time.monotonic()
        try:
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > self.timeout:
                    self._kill(proc)
                    raise AdapterError("TIMEOUT", f"Model exceeded its {self.timeout}s time limit.")
                _, pct, _ = parsers.read_frame_csv(progress_csv) if media_type == "video" else ([], None, None)
                if pct is not None:
                    pct = pct if pct > 1 else pct * 100
                    ctx.progress(5 + 0.9 * min(pct, 100), f"Analyzing frames ({min(pct, 100):.0f}%)")
                else:
                    # Time-based estimate so the bar keeps moving for image models.
                    ctx.progress(min(90.0, 5 + 85 * (1 - 1 / (1 + elapsed / 20))), "Running inference")
                time.sleep(1.0)
        except Canceled:
            self._kill(proc)
            raise
        for t in threads:
            t.join(timeout=5)
        stdout, stderr = "".join(stdout_lines), "".join(stderr_lines)
        ctx.progress(95, "Parsing results", force=True)
        try:
            return self._result(proc.returncode, stdout, stderr, stem, media_type, ctx, progress_csv)
        finally:
            self._collect(stem, ctx)

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)

    def _result(self, code: int, stdout: str, stderr: str, stem: str, media_type: str, ctx: TaskContext,
                progress_csv: Path) -> ModelResult:
        parser = self.spec.get("parser", "standard")
        no_face = parsers.detect_no_face(stdout, stderr)
        if code != 0:
            # Staff-only detail (error_detail); users see the classified code only.
            tail = stderr.strip().splitlines()[-20:] if stderr.strip() else []
            if any(m in stderr for m in OOM_MARKERS):
                raise AdapterError("GPU_OOM", "The GPU ran out of memory.")
            if any(m in stderr for m in ARCH_MARKERS):
                raise AdapterError("GPU_UNSUPPORTED", "This model's environment does not support the assigned GPU.")
            if no_face and self.model.get("face_required"):
                return ModelResult(no_face=True)
            raise AdapterError("RUNTIME_ERROR", f"Exit code {code}: {' | '.join(tail)[-3000:]}")

        if parser == "b2":
            prob = parsers.parse_b2(stdout)
        elif parser == "center":
            prob = parsers.parse_center(stdout)
        elif parser == "safe_csv":
            rf = self.spec.get("result_file")
            result_file = Path(rf.format(workdir=ctx.workdir)) if rf else None
            prob = parsers.parse_safe_csv(stdout, result_file)
        else:
            prob = parsers.parse_standard(stdout)

        per_frame, _, total = parsers.read_frame_csv(progress_csv)
        if prob is None and total is not None:
            prob = total
        faces = parsers.parse_faces(stdout)
        fallback = None
        if "SKKU_P_NO_FACE_DETECTED" in stdout and self.model.get("fallbacks", {}).get("on_no_face"):
            fallback = {"model": self.model["fallbacks"]["on_no_face"], "reason": "no face detected"}
        if prob is None:
            if no_face:
                return ModelResult(no_face=True)
            raise AdapterError("PARSE_ERROR", "The model finished but printed no score.")
        return ModelResult(fake_prob=round(prob, 6), faces=faces, per_frame=per_frame, fallback=fallback)

    def _collect(self, stem: str, ctx: TaskContext) -> None:
        """Upload XAI/face/video artifacts written by legacy scripts, then remove them."""
        root = config().models_root
        for sub in OUTPUT_DIRS:
            folder = root / sub
            if not folder.exists():
                continue
            for path in sorted(folder.glob(f"{stem}*")):
                if not path.is_file():
                    continue
                name = path.name.lower()
                suffix = path.suffix.lower()
                if suffix in IMAGE_SUFFIXES:
                    kind = "face" if "_face_" in name and "gradcam" not in name else "xai"
                    label = _label_for(name, stem)
                    ctx.add_artifact(path, kind=kind, label=label)
                elif suffix == ".mp4":
                    ctx.add_artifact(path, kind="video", label="Annotated video")
                elif suffix in (".csv", ".json"):
                    ctx.add_artifact(path, kind="frames", label="Per-frame scores" if suffix == ".csv" else "Faces")
                with contextlib.suppress(OSError):
                    path.unlink()


def _label_for(name: str, stem: str) -> str:
    base = name.rsplit(".", 1)[0]
    rest = base[len(stem):].strip("_.") or "original"
    return {"gradcam": "Grad-CAM", "face_gradcam": "Face Grad-CAM", "face_map": "Face map",
            "original": "Original"}.get(rest, rest.replace("_", " "))
