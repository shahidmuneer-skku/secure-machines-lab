"""Stdout / CSV parsers ported from the legacy Node pipeline (routs.js)."""

from __future__ import annotations

import contextlib
import csv
import json
import re
from pathlib import Path
from typing import Any

NUM = r"([0-9]*\.?[0-9]+(?:e[+-]?\d+)?)"
FAKE_PROB = re.compile(r"Fake Prob[:\s]*" + NUM, re.IGNORECASE)
AGG_FAKE_PROB = re.compile(r"Aggregated FAKE Prob[:\s]*" + NUM, re.IGNORECASE)
REAL = re.compile(r"real\s*:?\s*" + NUM, re.IGNORECASE)
FAKE = re.compile(r"fake\s*:?\s*" + NUM, re.IGNORECASE)
B2_REAL = re.compile(r"Average Real Probability:\s*(?:tensor\s*\(\s*)?([0-9.eE+-]+)", re.IGNORECASE)
B2_FAKE = re.compile(r"Average Fake Probability:\s*(?:tensor\s*\(\s*)?([0-9.eE+-]+)", re.IGNORECASE)
PREDICTION = re.compile(r"prediction[:\s]*([0-9.eE+-]+)", re.IGNORECASE)
FACES_JSON = re.compile(r"FACES_JSON:(\{.*\})", re.MULTILINE)
NO_FACE_MARKERS = ("SKKU_P_NO_FACE_DETECTED", "No faces detected", "얼굴을 찾지 못했습니다", "NO_FACE_DETECTED",
                   "no face detected")


def to_percent(value: str | float) -> float | None:
    """Legacy semantics: values in [0,1] are probabilities, (1,100] already percents."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= v <= 1:
        return v * 100
    if 1 < v <= 100:
        return v
    return None


def _normalize(real: float | None, fake: float | None) -> float | None:
    """Returns fake probability in [0, 1]."""
    if fake is None and real is None:
        return None
    if fake is None:
        fake = 100 - real  # type: ignore[operator]
    if real is not None and real + fake > 0 and abs(real + fake - 100) > 1:
        fake = fake * 100 / (real + fake)
    return max(0.0, min(1.0, fake / 100))


def parse_standard(stdout: str) -> float | None:
    m = FAKE_PROB.search(stdout)
    if m:
        return _normalize(None, to_percent(m.group(1)))
    m = AGG_FAKE_PROB.search(stdout)
    if m:
        return _normalize(None, to_percent(m.group(1)))
    # Last "real:"/"fake:" pair wins (scripts may print intermediate values).
    reals, fakes = REAL.findall(stdout), FAKE.findall(stdout)
    if reals and fakes:
        return _normalize(to_percent(reals[-1]), to_percent(fakes[-1]))
    return None


def parse_b2(stdout: str) -> float | None:
    r, f = B2_REAL.search(stdout), B2_FAKE.search(stdout)
    if r and f:
        return _normalize(to_percent(r.group(1)), to_percent(f.group(1)))
    return None


def parse_center(stdout: str) -> float | None:
    reals, fakes = REAL.findall(stdout), FAKE.findall(stdout)
    if reals and fakes:
        # Center-I prints 0-100 percentages already.
        real, fake = float(reals[-1]), float(fakes[-1])
        if real <= 1 and fake <= 1:
            real, fake = real * 100, fake * 100
        return _normalize(real, fake)
    return parse_standard(stdout)


def parse_safe_csv(stdout: str, result_file: Path | None) -> float | None:
    if result_file and result_file.exists():
        with result_file.open(newline="") as fh:
            rows = list(csv.reader(fh))
        if len(rows) > 1:
            header = [h.strip().lower() for h in rows[0]]
            last = rows[-1]
            value = None
            if "prediction" in header and len(last) > header.index("prediction"):
                value = last[header.index("prediction")].strip().strip("\"'")
            elif last:
                value = last[-1]
            pct = to_percent(value) if value is not None else None
            if pct is not None:
                return _normalize(None, pct)
    m = PREDICTION.search(stdout)
    return _normalize(None, to_percent(m.group(1))) if m else parse_standard(stdout)


def parse_faces(stdout: str) -> list[dict[str, Any]]:
    m = FACES_JSON.search(stdout)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        faces = data.get("faces", []) if isinstance(data, dict) else []
        return [f for f in faces if isinstance(f, dict)][:50]
    except ValueError:
        return []


def detect_no_face(stdout: str, stderr: str) -> bool:
    blob = stdout + "\n" + stderr
    return any(marker in blob for marker in NO_FACE_MARKERS)


def read_frame_csv(path: Path) -> tuple[list[dict[str, Any]], float | None, float | None]:
    """Legacy inference_csv/<stem>.csv → (per-frame rows, last progress %, total fake prob)."""
    if not path.exists():
        return [], None, None
    rows: list[dict[str, Any]] = []
    progress = None
    total = None
    try:
        with path.open(newline="") as fh:
            reader = csv.reader(fh)
            next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                label = row[0].strip()
                real, fake = to_percent(row[1]), to_percent(row[2])
                if len(row) >= 5:
                    with contextlib.suppress(ValueError):
                        progress = float(row[4])
                if label.lower().startswith("total"):
                    total = _normalize(real, fake)
                    continue
                if fake is not None:
                    rows.append({"frame": label, "fake_prob": round(fake / 100, 5)})
    except OSError:
        return [], None, None
    return rows, progress, total
