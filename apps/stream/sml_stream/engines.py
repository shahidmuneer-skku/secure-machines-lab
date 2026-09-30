"""The legacy long-form engines, imported unchanged from LONG_VIDEO_ROOT.

SKKU-AIGC runs in this process (loaded once); SKKU (BEYBI), SKKU-P2 and SKKU-P3 run as
subprocesses in their own conda environments through the legacy `external_models` package.
All expose `analyze_range_stream(...)`, yielding `meta`, `interval` and `done` events.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable, Iterator
from typing import Any

from . import settings

_BACKEND_DIR = settings.LONG_VIDEO_ROOT / "realtime_stream_app" / "backend"
_lock = threading.Lock()
_builtin: Any = None

BUILTIN = {"model_id": "skku-aigc", "canonical_id": "SKKU-AIGC", "name": "SKKU-AIGC"}
_BUILTIN_ALIASES = {"skku-aigc", "skku_aigc", "skkuaigc"}


def _import_path() -> None:
    for path in (str(_BACKEND_DIR), str(settings.LONG_VIDEO_ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)


def builtin_engine() -> Any:
    global _builtin
    with _lock:
        if _builtin is None:
            _import_path()
            from inference_engine import StreamingInferenceEngine  # legacy module

            engine = StreamingInferenceEngine(batch_size=6)
            engine.load_model()
            _builtin = engine
        return _builtin


def _external(model_id: str) -> Any:
    _import_path()
    import external_models  # legacy package

    return external_models.get_engine(model_id)


def resolve(model_id: str) -> Any:
    """The engine for a model id, or None when this service cannot run it."""
    key = (model_id or "").strip().lower()
    if key in _BUILTIN_ALIASES:
        return builtin_engine()
    return _external(key)


def is_builtin(engine: Any) -> bool:
    return engine is not None and engine is _builtin


def catalog() -> list[dict[str, Any]]:
    _import_path()
    import external_models

    checkpoint = settings.LONG_VIDEO_ROOT / "SafeChallenge" / "videoCheckpoint.pt"
    items = [{**BUILTIN, "runner": "builtin", "available": checkpoint.exists(),
              "reason": "" if checkpoint.exists() else f"missing checkpoint {checkpoint.name}",
              "face_crop": {"support": "optional", "default": False}}]
    items += [{k: v for k, v in e.items() if k in ("model_id", "canonical_id", "name", "runner", "available",
                                                    "reason", "face_crop")} for e in external_models.describe_engines()]
    return items


def face_crop_for(engine: Any, requested: bool | None) -> bool:
    """Same rule as the legacy service: 'always' crops, 'none' never, otherwise the request or default."""
    support = getattr(engine, "face_crop_support", "none")
    if support == "always":
        return True
    if support == "none":
        return False
    return bool(getattr(engine, "face_crop_default", False)) if requested is None else bool(requested)


def release_gpu_cache() -> None:
    """Free the in-process engine's cached VRAM before an external detector loads (legacy behaviour)."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001, S110 - best effort
        pass


def run(engine: Any, path: str, *, interval: float, start: float, end: float, whole: bool, face_crop: bool,
        should_stop: Callable[[], bool]) -> Iterator[dict[str, Any]]:
    """Events for one scan, exactly as the legacy service produced them."""
    if whole and is_builtin(engine):
        # Complete-video mode reproduces Safe/inference_video.py (first N whole clips).
        result = engine.analyze_full_video(path, num_clips=engine.WHOLE_VIDEO_CLIPS, face_crop=face_crop,
                                           should_stop=should_stop)
        prob = float(result["fake_probability"])
        yield {"type": "meta", "duration_sec": end, "start_sec": start, "end_sec": end, "interval_sec": end - start,
               "num_intervals": 1, "face_crop": bool(result.get("face_crop")), "summary_statistic": "mean"}
        yield {"type": "interval", "index": 0, "start_sec": start, "end_sec": end,
               "frames_used": int(result.get("frames_used") or 0), "fake_probability": prob}
        yield {"type": "done", "average_fake_probability": prob, "verdict": "FAKE" if prob >= 0.5 else "REAL",
               "frames_analyzed": int(result.get("frames_used") or 0), "summary_statistic": "mean"}
        return
    if not is_builtin(engine):
        release_gpu_cache()
    yield from engine.analyze_range_stream(
        path, interval_sec=(max(0.001, end - start) if whole else interval), start_sec=start, end_sec=end,
        should_stop=should_stop, face_crop=face_crop, whole_video=whole,
    )


def summary(state: dict[str, Any]) -> float:
    """Headline number: frame vote share for 'vote' detectors (BEYBI), else mean P(fake)."""
    if state.get("summary_statistic") == "vote":
        scored = int(state.get("frames_scored") or 0)
        return float(state.get("frames_voted_fake") or 0) / scored if scored else 0.0
    probs = [float(i["fake_probability"]) for i in state.get("intervals", [])]
    return sum(probs) / len(probs) if probs else 0.0
