"""Metadata & provenance analysis: EXIF, PNG text chunks, XMP and C2PA manifests.

AI-generation indicators come from EXIEF (`sml_worker.exief`, the owner's ExifTool-based
scorer): every tag ExifTool reads is checked against EXIEF's weighted signals, giving a score and
a verdict (confirmed / suspect / weak / unknown). The API weighs that verdict into the
AI-generation analysis. Metadata the file itself marks as broken - an ExifTool error or corruption
warning, or a C2PA manifest that fails validation - is reported as untrustworthy and not counted.
Without ExifTool the older built-in checks below still run. Missing camera EXIF is context, never
proof.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import av
from PIL import ExifTags, Image

from .. import exief
from ..config import config
from ..context import TaskContext
from .base import ModelResult

logger = logging.getLogger(__name__)

GENERATOR_PATTERNS = [
    (re.compile(r"midjourney", re.IGNORECASE), "Midjourney"),
    (re.compile(r"dall[\s·\-]?e|openai", re.IGNORECASE), "OpenAI DALL·E / GPT image"),
    (re.compile(r"stable[\s\-]?diffusion|sdxl|automatic1111|a1111|stability\.ai", re.IGNORECASE), "Stable Diffusion"),
    (re.compile(r"comfyui", re.IGNORECASE), "ComfyUI"),
    (re.compile(r"novelai", re.IGNORECASE), "NovelAI"),
    (re.compile(r"adobe firefly|firefly", re.IGNORECASE), "Adobe Firefly"),
    (re.compile(r"imagen|gemini|made with google ai|nano[\s\-]?banana", re.IGNORECASE), "Google Imagen / Gemini"),
    (re.compile(r"bing image creator|microsoft designer", re.IGNORECASE), "Microsoft Designer / Bing"),
    (re.compile(r"leonardo\.ai|ideogram|flux\.1|black forest labs|recraft|playground ai", re.IGNORECASE),
     "Other generator"),
    (re.compile(r"\bsora\b|runway(ml)?|pika labs|\bkling\b|luma dream machine|veo\b", re.IGNORECASE),
     "AI video generator"),
    (re.compile(r"\bai[\s\-]generated\b|generated (by|with) ai", re.IGNORECASE), "Self-declared AI generated"),
]
DIGITAL_SOURCE_AI = ("trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia", "algorithmicmedia")
SD_CHUNK_KEYS = ("parameters", "prompt", "workflow", "sd-metadata", "invokeai_metadata", "dream")


def _c2patool() -> str | None:
    candidates = [config().models_root / "meta_data" / "bin" / "c2patool", Path(shutil.which("c2patool") or "")]
    for c in candidates:
        if c and c.is_file():
            return str(c)
    return None


def _read_c2pa(path: Path) -> dict[str, Any]:
    tool = _c2patool()
    if not tool:
        return {"status": "tool_unavailable"}
    try:
        proc = subprocess.run([tool, str(path)], capture_output=True, text=True, timeout=60,
                              check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "error"}
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out.startswith("{"):
        return {"status": "none"}
    try:
        data = json.loads(out)
    except ValueError:
        return {"status": "error"}
    active = data.get("active_manifest")
    manifest = (data.get("manifests") or {}).get(active, {}) if active else {}
    generator = manifest.get("claim_generator") or ""
    info = manifest.get("claim_generator_info") or []
    if info and isinstance(info, list):
        generator = generator or info[0].get("name", "")
    sources = []
    for assertion in manifest.get("assertions") or []:
        blob = json.dumps(assertion).lower()
        for key in DIGITAL_SOURCE_AI:
            if key in blob:
                sources.append(key)
    # "Invalid" means the manifest or the file was altered after signing. A signer that is merely
    # not on c2patool's trust list (signingCredential.untrusted, e.g. OpenAI's) stays "Valid".
    statuses = data.get("validation_status") or []
    untrusted = any(st.get("code") == UNTRUSTED for st in statuses)
    failures = [f.get("code", "") for f in ((data.get("validation_results") or {}).get("activeManifest") or {})
                .get("failure") or [] if f.get("code") != UNTRUSTED]
    state = str(data.get("validation_state") or "").lower()
    invalid = state == "invalid" if state else bool(failures) or any(st.get("code") != UNTRUSTED for st in statuses)
    return {"status": "invalid_signature" if invalid else "valid", "generator": generator,
            "ai_source_types": sorted(set(sources)), "untrusted_signer": untrusted, "failures": failures[:5],
            "signer": (manifest.get("signature_info") or {}).get("issuer", "")}


UNTRUSTED = "signingCredential.untrusted"

# --- EXIEF ---------------------------------------------------------------------------------------

# The flags EXIEF's own exif.py uses, so its signals see the same tags.
EXIFTOOL_FLAGS = ["-j", "-a", "-G", "-charset", "filename=utf8", "-api", "largefilesupport=1"]

# ExifTool warnings that mean the file's metadata is damaged (non-"[minor]" ones only). The
# "Text/EXIF chunk(s) found after PNG IDAT" warning is an EXIEF signal, not damage.
CORRUPTION_RE = re.compile(
    r"corrupt|truncat|unexpected end|crc error|error reading|not a valid|"
    r"bad [\w\s]{0,30}(offset|size|length|format|header|directory)|"
    r"invalid [\w\s]{0,30}(structure|header|chunk|segment|ifd|directory)|missing (required|ifd)",
    re.IGNORECASE)

# Signal categories shown to users as evidence. Absence signals (no camera EXIF / thumbnail) fire on
# nearly every shared image, and provenance resets are context, so neither is listed as evidence.
EVIDENCE_SOURCE = {
    "explicit generator watermark": "Generator declaration",
    "structural artifact": "File structure",
    "resolution fingerprint": "Resolution",
    "editing provenance": "Editing history",
}


def _exiftool_cmd() -> list[str] | None:
    """EXIFTOOL_PATH, else ExifTool from the meta_data conda env run by that env's Perl (the
    script's `env perl` would pick the system Perl, which lacks Image::ExifTool), else PATH."""
    override = os.environ.get("EXIFTOOL_PATH", "").strip()
    if override:
        return [override]
    env_bin = config().conda_root / "envs" / "meta_data" / "bin"
    if (env_bin / "exiftool").is_file() and (env_bin / "perl").is_file():
        return [str(env_bin / "perl"), str(env_bin / "exiftool")]
    found = shutil.which("exiftool")
    return [found] if found else None


def _read_exiftool(path: Path) -> tuple[dict[str, Any] | None, str]:
    cmd = _exiftool_cmd()
    if not cmd:
        return None, "tool_unavailable"
    try:
        proc = subprocess.run([*cmd, *EXIFTOOL_FLAGS, str(path)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120, check=False)
        data = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        logger.warning("ExifTool failed on %s", path, exc_info=True)
        return None, "error"
    return (data[0], "ok") if data else (None, "error")


def _untrustworthy(rec: dict[str, Any], c2pa: dict[str, Any]) -> list[str]:
    """Why the file's own metadata cannot be relied on (owner, 2026-10-01): ExifTool errors or
    corruption warnings, and C2PA manifests that fail validation."""
    reasons = []
    for key, value in rec.items():
        if not key.startswith(("ExifTool:Error", "ExifTool:Warning")):
            continue
        for item in value if isinstance(value, list) else [value]:
            msg = str(item)
            if "after png idat" in msg.lower():
                continue
            if key.startswith("ExifTool:Error") or (not msg.startswith("[minor]") and CORRUPTION_RE.search(msg)):
                reasons.append(f"ExifTool: {msg[:200]}")
    if c2pa.get("status") == "invalid_signature":
        failed = ", ".join(c2pa.get("failures") or [])
        reasons.append("C2PA manifest failed validation" + (f" ({failed})" if failed else ""))
    return reasons


def run_exief(path: Path, c2pa: dict[str, Any]) -> dict[str, Any]:
    """EXIEF score, verdict and fired signals for one file (`status` is "ok" when it ran)."""
    rec, status = _read_exiftool(path)
    if rec is None:
        return {"status": status}
    result = exief.analyze_records([rec])[0]
    signals = []
    for sid in result["firedSignals"]:
        sig = exief.SIGNALS_BY_ID[sid]
        rows = result["evidence"].get(sid) or []
        shown = [f"{r['tag']} = {r['value']}" for r in rows if r.get("present") and r.get("value")][:2]
        signals.append({"id": sid, "label": sig.label, "tier": sig.tier, "category": sig.category,
                        "weight": sig.weight, "evidence": shown})
    return {"status": "ok", "score": int(result["score"]), "verdict": result["verdict"],
            "generator": result["generator"], "signals": signals, "untrustworthy": _untrustworthy(rec, c2pa)}


def _exief_evidence(report: dict[str, Any]) -> list[dict[str, str]]:
    """What users see: the signals behind a weak-or-stronger verdict. Below that EXIEF found nothing
    worth reporting. `size_proven` is left out: for a single file it only repeats the file's own
    declaration ("proven in this batch" by itself)."""
    if report["verdict"] == "unknown":
        return []
    evidence = []
    for sig in report["signals"]:
        source = EVIDENCE_SOURCE.get(sig["category"])
        if source is None or sig["id"] == "size_proven":
            continue
        detail = sig["label"]
        if sig["tier"] == 1 and report.get("generator"):
            detail = f"{detail} — {report['generator']}"
        evidence.append({"source": source, "strength": "strong" if sig["tier"] == 1 else "weak", "detail": detail})
    return evidence


def _image_fields(path: Path) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    with Image.open(path) as img:
        fields["format"] = img.format
        exif = img.getexif()
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name in ("Make", "Model", "Software", "DateTime", "Artist", "ImageDescription", "Copyright",
                        "HostComputer"):
                fields[name] = str(value)[:500]
        try:
            ifd = exif.get_ifd(ExifTags.IFD.Exif)
            for tag_id in (0x9003, 0x9286, 0xA434):  # DateTimeOriginal, UserComment, LensModel
                if tag_id in ifd:
                    fields[ExifTags.TAGS.get(tag_id, str(tag_id))] = str(ifd[tag_id])[:500]
        except Exception:
            logger.debug("Could not read the EXIF sub-IFD", exc_info=True)
        for key, value in (img.info or {}).items():
            if isinstance(value, (str, bytes)) and key.lower() not in ("icc_profile", "exif"):
                text = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
                fields[f"info:{key}"] = text[:2000]
        xmp = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
        if xmp:
            fields["xmp"] = (xmp.decode("utf-8", "ignore") if isinstance(xmp, bytes) else str(xmp))[:8000]
    if "xmp" not in fields:
        raw = path.read_bytes()[:2_000_000]
        m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.DOTALL)
        if m:
            fields["xmp"] = m.group(0).decode("utf-8", "ignore")[:8000]
    return fields


def _video_fields(path: Path) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    with av.open(str(path)) as container:
        for k, v in (container.metadata or {}).items():
            fields[k] = str(v)[:500]
        for stream in container.streams:
            for k, v in (stream.metadata or {}).items():
                fields[f"{stream.type}:{k}"] = str(v)[:500]
    return fields


def analyze(path: Path, media_type: str) -> dict[str, Any]:
    notes = []
    try:
        fields = _image_fields(path) if media_type == "image" else _video_fields(path)
    except (OSError, ValueError, av.FFmpegError):  # damaged file: ExifTool and C2PA still report on it
        logger.warning("Could not read %s with the image/video library", path, exc_info=True)
        fields = {}
        notes.append("Part of the file could not be read; it may be damaged.")
    c2pa = _read_c2pa(path)
    report = run_exief(path, c2pa)
    camera = " ".join(filter(None, [fields.get("Make"), fields.get("Model")])) or None
    if media_type == "image" and not camera:
        notes.append("No camera make/model in EXIF (common for screenshots, edits and AI images).")
    if report["status"] != "ok":
        return {**_builtin_indicators(fields, c2pa), "exief": report, "camera": camera,
                "software": fields.get("Software") or fields.get("encoder"), "c2pa_status": c2pa.get("status"),
                "c2pa": c2pa, "notes": notes, "fields": _visible(fields)}
    trusted = not report["untrustworthy"]
    if not trusted:
        notes.append("The file's metadata looks damaged or altered, so these indicators were not counted.")
    return {
        "ai_generated": trusted and report["verdict"] == "confirmed",
        "confidence": ({"confirmed": "strong", "suspect": "weak", "weak": "weak"}.get(report["verdict"], "none")
                       if trusted else "none"),
        "evidence": _exief_evidence(report),
        "exief": report,
        "camera": camera,
        "software": fields.get("Software") or fields.get("encoder"),
        "c2pa_status": c2pa.get("status"),
        "c2pa": c2pa,
        "notes": notes,
        "fields": _visible(fields),
    }


def _visible(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if k != "xmp" and not k.startswith("info:parameters")}


def _builtin_indicators(fields: dict[str, Any], c2pa: dict[str, Any]) -> dict[str, Any]:
    """The pre-EXIEF checks, used only when ExifTool is unavailable."""
    evidence: list[dict[str, str]] = []

    if c2pa.get("ai_source_types"):
        evidence.append({"source": "C2PA", "strength": "strong",
                         "detail": f"Content Credentials declare {', '.join(c2pa['ai_source_types'])}"
                                   + (f" (generator: {c2pa['generator']})" if c2pa.get("generator") else "")})
    blob = " ".join(str(v) for v in fields.values())
    xmp = str(fields.get("xmp", "")).lower()
    for key in DIGITAL_SOURCE_AI:
        if key in xmp:
            evidence.append({"source": "XMP / IPTC", "strength": "strong",
                             "detail": f"IPTC DigitalSourceType = {key}"})
            break
    for key, value in fields.items():
        if key.startswith("info:") and key[5:].lower() in SD_CHUNK_KEYS and len(str(value)) > 10:
            evidence.append({"source": "PNG text chunk", "strength": "strong",
                             "detail": f"Generation parameters embedded in '{key[5:]}' chunk"})
            break
    software = " ".join(str(fields.get(k, "")) for k in ("Software", "HostComputer", "encoder", "comment",
                                                          "com.apple.quicktime.software"))
    for pattern, name in GENERATOR_PATTERNS:
        if pattern.search(software) or (c2pa.get("generator") and pattern.search(c2pa["generator"])):
            evidence.append({"source": "Software tag", "strength": "strong", "detail": f"Generator: {name}"})
            break
        if pattern.search(blob):
            evidence.append({"source": "Metadata text", "strength": "weak", "detail": f"Mentions {name}"})
            break

    strong = [e for e in evidence if e["strength"] == "strong"]
    return {"ai_generated": bool(strong), "confidence": "strong" if strong else ("weak" if evidence else "none"),
            "evidence": evidence}


class MetadataAdapter:
    id = "metadata"

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        ctx.log("Reading EXIF / XMP / C2PA provenance")
        ctx.progress(20, "Reading metadata", force=True)
        report = analyze(media_path, media_type)
        ex = report.get("exief") or {}
        if ex.get("status") == "ok":
            ctx.log(f"EXIEF: {ex['verdict']} (score {ex['score']})"
                    + (f", not counted: {'; '.join(ex['untrustworthy'])}" if ex["untrustworthy"] else ""))
        if report["ai_generated"]:
            ctx.log("AI-generation indicator found in metadata")
        summary = ("AI-generation indicator in metadata" if report["ai_generated"]
                   else "No AI-generation indicators in metadata")
        return ModelResult(extra={"ai_indicators": report, "summary": summary})
