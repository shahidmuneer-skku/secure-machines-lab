"""Metadata & provenance analysis: EXIF, PNG text chunks, XMP and C2PA manifests.

Flags AI-generation *indicators*. Only strong evidence (a C2PA/IPTC digital
source type of trainedAlgorithmicMedia, generator parameters embedded by
Stable Diffusion/ComfyUI/NovelAI, or an explicit generator software tag) sets
`ai_generated`. Missing camera EXIF is reported as context, never as proof.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import av
from PIL import ExifTags, Image

from ..config import config
from ..context import TaskContext
from .base import ModelResult

GENERATOR_PATTERNS = [
    (re.compile(r"midjourney", re.I), "Midjourney"),
    (re.compile(r"dall[\s·\-]?e|openai", re.I), "OpenAI DALL·E / GPT image"),
    (re.compile(r"stable[\s\-]?diffusion|sdxl|automatic1111|a1111|stability\.ai", re.I), "Stable Diffusion"),
    (re.compile(r"comfyui", re.I), "ComfyUI"),
    (re.compile(r"novelai", re.I), "NovelAI"),
    (re.compile(r"adobe firefly|firefly", re.I), "Adobe Firefly"),
    (re.compile(r"imagen|gemini|made with google ai|nano[\s\-]?banana", re.I), "Google Imagen / Gemini"),
    (re.compile(r"bing image creator|microsoft designer", re.I), "Microsoft Designer / Bing"),
    (re.compile(r"leonardo\.ai|ideogram|flux\.1|black forest labs|recraft|playground ai", re.I), "Other generator"),
    (re.compile(r"\bsora\b|runway(ml)?|pika labs|\bkling\b|luma dream machine|veo\b", re.I), "AI video generator"),
    (re.compile(r"\bai[\s\-]generated\b|generated (by|with) ai", re.I), "Self-declared AI generated"),
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
        proc = subprocess.run([tool, str(path)], capture_output=True, text=True, timeout=60,  # noqa: S603
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
    status = "valid" if not data.get("validation_status") else "invalid_signature"
    return {"status": status, "generator": generator, "ai_source_types": sorted(set(sources)),
            "signer": (manifest.get("signature_info") or {}).get("issuer", "")}


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
        except Exception:  # noqa: BLE001
            pass
        for key, value in (img.info or {}).items():
            if isinstance(value, (str, bytes)) and key.lower() not in ("icc_profile", "exif"):
                text = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
                fields[f"info:{key}"] = text[:2000]
        xmp = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
        if xmp:
            fields["xmp"] = (xmp.decode("utf-8", "ignore") if isinstance(xmp, bytes) else str(xmp))[:8000]
    if "xmp" not in fields:
        raw = path.read_bytes()[:2_000_000]
        m = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S)
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
    fields = _image_fields(path) if media_type == "image" else _video_fields(path)
    c2pa = _read_c2pa(path)
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

    camera = " ".join(filter(None, [fields.get("Make"), fields.get("Model")])) or None
    strong = [e for e in evidence if e["strength"] == "strong"]
    notes = []
    if media_type == "image" and not camera:
        notes.append("No camera make/model in EXIF (common for screenshots, edits and AI images).")
    return {
        "ai_generated": bool(strong),
        "confidence": "strong" if strong else ("weak" if evidence else "none"),
        "evidence": evidence,
        "camera": camera,
        "software": fields.get("Software") or fields.get("encoder"),
        "c2pa_status": c2pa.get("status"),
        "c2pa": c2pa,
        "notes": notes,
        "fields": {k: v for k, v in fields.items() if k != "xmp" and not k.startswith("info:parameters")},
    }


class MetadataAdapter:
    id = "metadata"

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult:
        ctx.log("Reading EXIF / XMP / C2PA provenance")
        ctx.progress(20, "Reading metadata", force=True)
        report = analyze(media_path, media_type)
        if report["ai_generated"]:
            ctx.log("AI-generation indicator found in metadata")
        summary = ("AI-generation indicator in metadata" if report["ai_generated"]
                   else "No AI-generation indicators in metadata")
        return ModelResult(extra={"ai_indicators": report, "summary": summary})
