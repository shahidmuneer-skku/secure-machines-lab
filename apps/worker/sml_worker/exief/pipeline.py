"""Turn raw exiftool records into scored, explainable results.

Scoring is two-pass: the first pass finds every file that carries an explicit
generator declaration, the second scores everything - so `size_proven` can ask
"is this pixel size used by a file we already proved is AI, in this same batch?"
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Iterable, Sequence

from .signals import (
    CATEGORY_ORDER, NAME_FALLBACK_FIELDS, PROMPT_FIELDS, SIGNALS, SIGNALS_BY_ID,
    SIGNED_COMMENT_RE, SOFTWARE_FIELDS, Record, aigc_label, aigc_producer_name,
    evidence_for, first, match_editor, match_vendor, modality_of, text, val, verdict_for,
)

TIER1 = [s for s in SIGNALS if s.tier == 1]


def media_id(path: str) -> str:
    return hashlib.sha1(os.path.abspath(path).encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _duration_seconds(rec: Record) -> float | None:
    raw = first(rec, "QuickTime:Duration", "Composite:Duration", "Matroska:Duration")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    m = re.match(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$", s)
    if m:
        h, mi, sec = m.groups()
        return int(h) * 3600 + int(mi) * 60 + float(sec)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*s?", s)
    return float(m.group(1)) if m else None


def _generator_name(rec: Record, fired: set[str]) -> str | None:
    """Who signed or declared the claim - reported, never scored."""
    name = first(rec, "JUMBF:Claim_Generator_InfoName", "JUMBF:ActionsSoftwareAgentName",
                 "JUMBF:Tool", "JUMBF:Claim_Generator")

    # the AIGC label names a registered producer, which beats any encoder string
    if not name:
        label = aigc_label(rec)
        if label:
            name = aigc_producer_name(label.get("ContentProducer"))
            src = label.get("source_info")
            if src and isinstance(src, str):
                name = f"{name} — {src}" if name else src

    if not name and "comfyui_workflow" in fired:
        name = "ComfyUI"
    # c2pa-rs is the generic signing library, not a vendor - name the model instead
    if name and name.strip().lower().startswith("c2pa-rs"):
        name = (first(rec, "JUMBF:ActionsParametersModel_Name", "JUMBF:ActionsSoftwareAgentName")
                or "c2pa-rs (unnamed)")
    if not name:
        name = match_vendor(text(rec, *SOFTWARE_FIELDS))
    if not name and "diffusion_params" in fired:
        # the recipe itself usually names the tool that wrote it
        name = match_vendor(text(rec, *PROMPT_FIELDS))
    if not name:
        name = match_editor(text(rec, *SOFTWARE_FIELDS))
    if not name:
        for field in NAME_FALLBACK_FIELDS:
            raw = first(rec, field)
            if raw and _is_name_like(raw):
                name = _tidy_software(raw)
                break
    if not name:
        if "aigc_chunk" in fired:
            # the label fired but named no producer - say that, do not guess a vendor
            name = "AIGC-labelled (producer not stated)"
        elif "recraft_sig" in fired:
            name = "Recraft"
        elif "diffusion_params" in fired:
            # the recipe is there but nothing in it names the tool
            name = "unnamed diffusion pipeline"
        elif "signed_comment" in fired:
            # an opaque vendor token; say so rather than guess the vendor
            name = "unidentified (signed Comment atom)"
    return name.strip() if isinstance(name, str) and name.strip() else None


# Muxer versions, track handlers and container boilerplate are plumbing. Reporting
# "Lavf58.76.100" or "SoundHandler" as the generator is worse than reporting nothing.
PLUMBING_RE = re.compile(
    r"^\s*(lav[fc]\d|ffmpeg|x26[45]|libav|"
    r"(video|sound|data|subtitle|metadata|timecode)handler|"
    r"iso media file produced by|core media|gpac|mp4box|bento4|"
    r"twitter-\w+ muxer|isom|mp42|qt\s*$)", re.I)


def _is_name_like(value: str) -> bool:
    """A tool name, not plumbing, a signature blob, a URL or a marketing sentence."""
    v = value.strip()
    if not v or len(v) > 60:
        return False
    if PLUMBING_RE.match(v) or SIGNED_COMMENT_RE.match(v):
        return False
    if "http://" in v or "https://" in v:
        return False
    return True


def _tidy_software(raw: str) -> str:
    """"Adobe Photoshop Web (2026.15.0.0 1029c966bc3) (Google Chrome)" -> "Adobe Photoshop Web"."""
    s = re.sub(r"\s*\([^)]*\)", "", raw)            # drop version / host parentheticals
    s = re.sub(r"\s+v?\d+(\.\d+)+\S*$", "", s)      # drop a trailing bare version
    return (s.strip() or raw.strip())[:60]


def _dimensions(rec: Record) -> tuple[int | None, int | None]:
    w = rec.get("File:ImageWidth") or rec.get("Composite:ImageWidth") or rec.get("EXIF:ExifImageWidth")
    h = rec.get("File:ImageHeight") or rec.get("Composite:ImageHeight") or rec.get("EXIF:ExifImageHeight")
    try:
        return (int(w) if w is not None else None, int(h) if h is not None else None)
    except (TypeError, ValueError):
        return (None, None)


def _clean_meta(rec: Record) -> dict[str, Any]:
    """Metadata for the detail view: drop ExifTool bookkeeping, keep everything else."""
    skip_prefixes = ("ExifTool:ExifToolVersion", "SourceFile")
    out = {}
    for k, v in rec.items():
        if k in skip_prefixes or k == "SourceFile":
            continue
        if isinstance(v, (dict, list)):
            v = str(v)
        out[k] = v
    return out


def analyze_records(records: Sequence[Record], *, display_root: str | None = None) -> list[dict]:
    ctxs: list[dict] = []
    for rec in records:
        ctxs.append({"duration_seconds": _duration_seconds(rec), "proven_sizes": ()})

    # pass 1 - which sizes are proven AI by an explicit declaration in this batch,
    # and which files did the proving (shown as the evidence behind `size_proven`)
    proven_sizes: set[str] = set()
    proven_sources: dict[str, list[str]] = {}
    tier1_hits: list[set[str]] = []
    for rec, ctx in zip(records, ctxs):
        m = modality_of(rec)
        hits = {s.id for s in TIER1 if s.applies_to(m) and s.detect(rec, ctx)}
        tier1_hits.append(hits)
        size = val(rec, "Composite:ImageSize")
        if hits and size:
            proven_sizes.add(size)
            proven_sources.setdefault(size, []).append(
                rec.get("File:FileName") or os.path.basename(rec.get("SourceFile") or ""))

    # pass 2 - full scoring
    results = []
    for rec, ctx, hits in zip(records, ctxs, tier1_hits):
        ctx["proven_sizes"] = proven_sizes
        ctx["proven_size_sources"] = proven_sources
        results.append(_score_one(rec, ctx, display_root))
    return results


def _score_one(rec: Record, ctx: dict, display_root: str | None) -> dict:
    modality = modality_of(rec)
    fired: dict[str, bool] = {}
    evidence: dict[str, list[dict]] = {}
    score = 0
    for s in SIGNALS:
        if not s.applies_to(modality):
            continue
        hit = bool(s.detect(rec, ctx))
        fired[s.id] = hit
        if hit:
            score += s.weight
            rows = evidence_for(s, rec, ctx)
            if rows:
                evidence[s.id] = rows

    fired_ids = {k for k, v in fired.items() if v}
    categories = [c for c in CATEGORY_ORDER
                  if any(SIGNALS_BY_ID[i].category == c for i in fired_ids)]
    # state the camera check either way, it is the one signal worth reading as a negative
    camera_present = not fired.get("no_camera_exif", fired.get("no_camera_video", True))
    if camera_present:
        categories = categories + ["camera metadata present"]

    source = rec.get("SourceFile") or ""
    abs_path = os.path.abspath(source) if source else ""
    directory = rec.get("File:Directory") or (os.path.dirname(abs_path) if abs_path else "")
    rel = None
    if display_root and abs_path:
        try:
            rel = os.path.relpath(abs_path, display_root)
        except ValueError:
            rel = None

    width, height = _dimensions(rec)
    size_bytes = rec.get("File:FileSize")
    if isinstance(size_bytes, str):
        size_bytes = _parse_filesize(size_bytes)

    return {
        "id": media_id(abs_path or source),
        "path": abs_path,
        "relPath": rel,
        "directory": directory,
        "fileName": rec.get("File:FileName") or os.path.basename(abs_path),
        "fileType": rec.get("File:FileType"),
        "mimeType": rec.get("File:MIMEType"),
        "modality": modality,
        "width": width,
        "height": height,
        "imageSize": val(rec, "Composite:ImageSize"),
        "megapixels": rec.get("Composite:Megapixels"),
        "fileSize": size_bytes,
        "durationSeconds": ctx.get("duration_seconds"),
        "createDate": first(rec, "EXIF:DateTimeOriginal", "EXIF:CreateDate",
                            "QuickTime:CreateDate", "XMP:CreateDate", "File:FileModifyDate"),
        "score": score,
        "verdict": verdict_for(score),
        "signals": fired,
        "evidence": evidence,
        "firedSignals": sorted(fired_ids, key=lambda i: (SIGNALS_BY_ID[i].tier, -SIGNALS_BY_ID[i].weight)),
        "categories": categories,
        "generator": _generator_name(rec, fired_ids),
        "cameraMake": first(rec, "EXIF:Make", "QuickTime:Make"),
        "cameraModel": first(rec, "EXIF:Model", "QuickTime:Model"),
        "software": first(rec, *SOFTWARE_FIELDS),
        "warnings": first(rec, "ExifTool:Warning"),
        "tagCount": len(rec),
        "metadata": _clean_meta(rec),
    }


def _parse_filesize(s: str) -> int | None:
    m = re.match(r"^([\d.]+)\s*(bytes|kB|KB|MB|GB|MiB|KiB|GiB)?$", s.strip())
    if not m:
        return None
    n = float(m.group(1))
    unit = (m.group(2) or "bytes").lower()
    mult = {"bytes": 1, "kb": 1024, "kib": 1024, "mb": 1024 ** 2, "mib": 1024 ** 2,
            "gb": 1024 ** 3, "gib": 1024 ** 3}
    return int(n * mult.get(unit, 1))


def summarize(results: Sequence[dict]) -> dict:
    """Aggregates the dashboard reads - computed server-side so exports match the UI."""
    by_verdict: dict[str, int] = {"confirmed": 0, "suspect": 0, "weak": 0, "unknown": 0}
    by_type: dict[str, int] = {}
    by_generator: dict[str, int] = {}
    by_signal: dict[str, int] = {}
    by_size: dict[str, int] = {}
    by_modality: dict[str, int] = {}
    scores: list[int] = []

    for r in results:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        by_type[r["fileType"] or "unknown"] = by_type.get(r["fileType"] or "unknown", 0) + 1
        by_modality[r["modality"]] = by_modality.get(r["modality"], 0) + 1
        if r["generator"]:
            by_generator[r["generator"]] = by_generator.get(r["generator"], 0) + 1
        for sid in r["firedSignals"]:
            by_signal[sid] = by_signal.get(sid, 0) + 1
        if r["imageSize"]:
            by_size[r["imageSize"]] = by_size.get(r["imageSize"], 0) + 1
        scores.append(r["score"])

    return {
        "total": len(results),
        "byVerdict": by_verdict,
        "byFileType": _sorted_counts(by_type),
        "byModality": by_modality,
        "byGenerator": _sorted_counts(by_generator),
        "bySignal": _sorted_counts(by_signal),
        "bySize": _sorted_counts(by_size)[:24],
        "scoreMax": max(scores) if scores else 0,
    }


def _sorted_counts(d: dict[str, int]) -> list[dict]:
    return [{"key": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))]
