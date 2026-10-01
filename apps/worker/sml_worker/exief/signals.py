"""Signal registry and scoring for AI-generated media detection from file metadata.

Every indicator is declared once here - weight, tier, human explanation and the
detector - so the API can ship the registry to the frontend and the UI can explain
a verdict without hard-coding anything about the rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

Record = dict[str, Any]

# --- modality ---------------------------------------------------------------

IMAGE_TYPES = {"JPEG", "PNG", "WEBP", "HEIC", "HEIF", "AVIF", "TIFF", "GIF", "BMP", "JP2", "DNG"}
VIDEO_TYPES = {"MP4", "MOV", "M4V", "AVI", "MKV", "WEBM", "MPEG", "MPG", "3GP", "3G2", "M2TS", "MTS", "WMV", "FLV"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".avif", ".tif", ".tiff", ".gif", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".3gp", ".wmv", ".flv"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


def modality_of(rec: Record) -> str:
    ftype = str(rec.get("File:FileType") or "").upper()
    if ftype in IMAGE_TYPES:
        return "image"
    if ftype in VIDEO_TYPES:
        return "video"
    mime = str(rec.get("File:MIMEType") or "")
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    return "other"


# --- small helpers over an exiftool record ----------------------------------


def val(rec: Record, key: str) -> Any:
    v = rec.get(key)
    if v is None or v == "":
        return None
    return v


def text(rec: Record, *keys: str) -> str:
    """Concatenated lowercase text of the given tags, for substring matching."""
    parts = []
    for k in keys:
        v = rec.get(k)
        if v is None or v == "":
            continue
        parts.append(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    return " ".join(parts).lower()


def first(rec: Record, *keys: str) -> str | None:
    for k in keys:
        v = val(rec, k)
        if v is None:
            continue
        return v if isinstance(v, str) else str(v)
    return None


def truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "yes", "1"}
    return bool(v) if isinstance(v, (int, float)) else False


# --- vendor vocabulary ------------------------------------------------------

# C2PA IPTC digital source type: the standardised "a model made this" declaration.
TRAINED = "trainedalgorithmicmedia"
COMPOSITE_WITH_TRAINED = "compositewithtrainedalgorithmicmedia"

SOFTWARE_FIELDS = (
    "EXIF:Software", "XMP:CreatorTool", "XMP:Software", "PNG:Software",
    "IPTC:OriginatingProgram", "QuickTime:Software", "QuickTime:Encoder",
    "QuickTime:HandlerDescription", "QuickTime:Comment", "XMP:HistorySoftwareAgent",
    "QuickTime:Title", "QuickTime:Author", "QuickTime:Information",
    "QuickTime:UserComment", "QuickTime:LvMetaInfo", "QuickTime:Model",
)

# Fields whose raw value may be shown as the tool that wrote the file. Muxer and
# container fields are excluded: QuickTime:Encoder is often a bare "Google" on a
# YouTube-muxed clip, and reporting that as the generator implies Veo.
NAME_FALLBACK_FIELDS = (
    "EXIF:Software", "XMP:CreatorTool", "XMP:Software", "PNG:Software",
    "IPTC:OriginatingProgram", "QuickTime:Software", "XMP:HistorySoftwareAgent",
)

PROMPT_FIELDS = (
    "PNG:Parameters", "PNG:Prompt", "PNG:Workflow", "PNG:Comment", "PNG:Description",
    "PNG:Dream", "PNG:Sd_metadata", "XMP:Prompt", "EXIF:UserComment", "File:Comment",
    "QuickTime:Prompt", "QuickTime:Workflow",
)

# ComfyUI writes its node graph into the container. In a full export that is the
# whole workflow; the VideoHelperSuite node leaves only a stub - both mean ComfyUI.
WORKFLOW_FIELDS = ("QuickTime:Workflow", "QuickTime:Prompt", "PNG:Workflow", "PNG:Prompt")

# China's CAC labelling rules (in force 2025-09-01) require generators to embed a
# machine-readable label. Images carry it in a PNG text chunk, video in a QuickTime
# user-data atom; the payload is the same JSON either way.
AIGC_FIELDS = ("PNG:AIGC", "QuickTime:AIGC", "XMP:AIGC", "QuickTime:UserComment")

# ContentProducer codes observed in the sample set. The ByteDance mapping is
# corroborated in-file: the same clips carry LvMetaInfo product "dreamina" /
# "commercepro_app". Unrecognised codes are reported verbatim rather than guessed at.
AIGC_PRODUCER_PREFIXES: list[tuple[str, str]] = [
    ("0011914403000886740", "ByteDance (Dreamina / Jimeng / Seedance)"),
    ("001191330106MA2CFLDG4R", "CN producer 91330106MA2CFLDG4R"),
]

# name patterns -> canonical vendor label, matched against software/claim fields
VENDOR_PATTERNS: list[tuple[str, str]] = [
    (r"midjourney", "Midjourney"),
    (r"stable\s*diffusion|automatic1111|a1111|sd\.next|invokeai|stability", "Stability AI / SD"),
    (r"comfyui", "ComfyUI"),
    (r"dall[\W_]?e", "OpenAI DALL-E"),
    (r"\bsora\b", "OpenAI Sora"),
    (r"openai|chatgpt|gpt-image", "OpenAI"),
    (r"firefly|adobe\s+generative", "Adobe Firefly"),
    (r"seedream|seedance|bytedance|dreamina|jimeng|dola-seed", "ByteDance Seedream"),
    (r"\bveo\b|imagen|nano.?banana|google c2pa|deepmind", "Google"),
    (r"black\s*forest|\bflux\b", "Black Forest Labs FLUX"),
    (r"recraft", "Recraft"),
    (r"ideogram", "Ideogram"),
    (r"leonardo", "Leonardo.Ai"),
    (r"runway", "Runway"),
    (r"kling|kuaishou", "Kling"),
    (r"luma\s*(ai|labs)|dream\s*machine", "Luma Dream Machine"),
    (r"\bpika\b", "Pika"),
    (r"hailuo|minimax", "MiniMax Hailuo"),
    (r"\bgrok\b|\bxai\b", "xAI Grok"),
    (r"qwen|wan2\.|tongyi|alibaba", "Alibaba Qwen/Wan"),
    # CapCut and Clipchamp are editors, not generators - they belong to EDITOR_RE only
    (r"dreamina|jimeng", "ByteDance (Dreamina / Jimeng)"),
    (r"hunyuan", "Tencent Hunyuan"),
    (r"\bvidu\b|shengshu", "Vidu"),
    (r"\bheygen\b|\bsynthesia\b|\bd-id\b|\bhedra\b|\bakool\b", "Avatar service"),
    (r"\bcanva\b.*(magic|ai)|magic\s*media", "Canva Magic Media"),
    (r"playground\s*ai|\bnovelai\b|\bfooocus\b|\bkrea\b|\bfreepik\b", "Other generator"),
]

VENDOR_RE = [(re.compile(p, re.I), name) for p, name in VENDOR_PATTERNS]


def match_vendor(blob: str) -> str | None:
    for rx, name in VENDOR_RE:
        if rx.search(blob):
            return name
    return None


# Tools that are not generators. Matched only to give a clean name to the tool that
# last wrote the file - never to score it as evidence of generation.
EDITOR_PATTERNS: list[tuple[str, str]] = [
    (r"clipchamp", "Microsoft Clipchamp"),
    (r"capcut|jianying", "CapCut"),
    (r"premiere", "Adobe Premiere"),
    (r"final cut", "Final Cut Pro"),
    (r"davinci", "DaVinci Resolve"),
    (r"photoshop", "Adobe Photoshop"),
    (r"lightroom", "Adobe Lightroom"),
    (r"\bgimp\b", "GIMP"),
    (r"replaykit", "iOS screen recording"),
    (r"filmora|camtasia|kdenlive|shotcut|vegas pro|imovie|inshot|kinemaster", "Video editor"),
]

EDITOR_RE_MAP = [(re.compile(p, re.I), name) for p, name in EDITOR_PATTERNS]


def match_editor(blob: str) -> str | None:
    for rx, name in EDITOR_RE_MAP:
        if rx.search(blob):
            return name
    return None


def aigc_label(rec: Record) -> dict | None:
    """Parse the CAC AIGC label, whichever container carries it.

    Returns the decoded payload, or None. `Label` arrives as "1" from some
    encoders and 1 from others, so it is normalised to a string.
    """
    for key in AIGC_FIELDS:
        raw = rec.get(key)
        if not raw:
            continue
        data = raw
        if isinstance(data, str):
            s = data.strip()
            if not s.startswith("{"):
                continue
            try:
                data = json.loads(s)
            except json.JSONDecodeError:
                continue
        if not isinstance(data, dict):
            continue
        if "Label" in data or "aigc_label_type" in data:
            out = dict(data)
            if "Label" in out:
                out["Label"] = str(out["Label"]).strip()
            out["_field"] = key
            return out
    return None


def aigc_producer_name(code: str | None) -> str | None:
    if not code:
        return None
    for prefix, name in AIGC_PRODUCER_PREFIXES:
        if code.startswith(prefix):
            return name
    return f"AIGC producer {code}"


# An opaque base64 blob under a "Signature:" prefix in the Comment atom. Not C2PA
# (no JUMBF box) and not the AIGC label (not JSON) - a vendor's own token.
SIGNED_COMMENT_RE = re.compile(r"^\s*signature:\s*[A-Za-z0-9+/=\s]{60,}$", re.I)


# canonical SDXL / Flux / DALL-E 3 latent-native sizes
NATIVE_IMAGE_SIZES = {
    "1024x1024", "1152x896", "896x1152", "1216x832", "832x1216", "1344x768",
    "768x1344", "1536x640", "640x1536", "1024x1536", "1536x1024",
    "1024x1792", "1792x1024", "1408x1024", "1024x1408", "1280x1280",
}

# Generation-native video frame sizes: squares and odd ratios that no camera
# produces. Camera-standard sizes are deliberately absent - see COMMON_CAPTURE_SIZES.
NATIVE_VIDEO_SIZES = {
    "1024x1024", "960x960", "1088x1088", "704x1280", "768x768", "512x512",
    "832x480", "480x832", "1024x576", "576x1024", "640x640", "720x720",
    "560x560", "480x640", "464x688", "688x464", "834x1112", "1112x834",
    "768x1152", "1152x768", "1248x720", "720x1248", "1280x768",
}

# Sizes so common in capture and delivery that sharing one with a confirmed AI file
# says nothing. Without this, a single 1280x720 generated clip would drag every
# 720p camera clip in the same batch up to "suspect" through `size_proven`.
COMMON_CAPTURE_SIZES = {
    "1920x1080", "1080x1920", "1280x720", "720x1280", "3840x2160", "2160x3840",
    "2560x1440", "1440x2560", "854x480", "640x360", "640x480", "1024x768",
    "1280x960", "1920x1440", "4096x2160", "1440x1080",
    "6000x4000", "4000x6000", "5184x3456", "4032x3024", "3024x4032", "4608x3456",
}


# --- signal registry --------------------------------------------------------


@dataclass(frozen=True)
class Signal:
    id: str
    label: str
    weight: int
    tier: int
    category: str
    modality: str  # "image" | "video" | "both"
    description: str
    detect: Callable[[Record, dict], bool] = field(compare=False, repr=False)
    #: the tags this signal reads - surfaced in the UI as the evidence behind it
    fields: tuple[str, ...] = ()
    #: overrides the generic tag dump where the interesting part is *what matched*
    explain: Callable[[Record, dict], list[dict]] | None = field(
        default=None, compare=False, repr=False)

    def applies_to(self, m: str) -> bool:
        return self.modality == "both" or self.modality == m


MAX_EVIDENCE_CHARS = 260


def fmt_value(v: Any) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = " ".join(s.split())
    if len(s) > MAX_EVIDENCE_CHARS:
        return f"{s[:MAX_EVIDENCE_CHARS]}… (+{len(s) - MAX_EVIDENCE_CHARS} more characters)"
    return s


def _row(tag: str, value: Any, present: bool = True, note: str | None = None) -> dict:
    return {"tag": tag, "value": fmt_value(value) if present and value is not None else None,
            "present": present, "note": note}


def evidence_for(sig: Signal, rec: Record, ctx: dict) -> list[dict]:
    """The tags that actually made this signal fire.

    Presence signals list only the tags that are there; absence signals fire
    *because* nothing is there, so they list every tag checked, marked absent.
    """
    if sig.explain is not None:
        return sig.explain(rec, ctx)
    present = [_row(f, rec[f]) for f in sig.fields if rec.get(f) not in (None, "")]
    if present:
        return present
    return [_row(f, None, present=False) for f in sig.fields]


CATEGORY_ORDER = [
    "explicit generator watermark",
    "structural artifact",
    "resolution fingerprint",
    "absence signal",
    "editing provenance",
    "provenance reset",
]


# -- tier 1: explicit declarations by the generator --------------------------

def _aigc_chunk(rec, ctx):
    """CAC AIGC label declaring Label=1. Label=0 is a declaration it is NOT AI."""
    d = aigc_label(rec)
    if not d:
        return False
    if "Label" in d:
        return d["Label"] in ("1", "true", "True")
    return False  # aigc_label_type alone is a container field, not a claim


def _comfyui_workflow(rec, ctx):
    return any(val(rec, f) is not None for f in WORKFLOW_FIELDS)


def _signed_comment(rec, ctx):
    for key in ("QuickTime:Comment", "QuickTime:UserComment", "EXIF:UserComment", "PNG:Comment"):
        v = val(rec, key)
        if isinstance(v, str) and SIGNED_COMMENT_RE.match(v):
            return True
    return False


def _recraft_sig(rec, ctx):
    return val(rec, "PNG:Recraft_signature") is not None


def _c2pa_trained(rec, ctx):
    blob = text(rec, "JUMBF:ActionsDigitalSourceType", "XMP:DigitalSourceType",
                "JUMBF:DigitalSourceType", "IPTC:DigitalSourceType")
    return TRAINED in blob or COMPOSITE_WITH_TRAINED in blob


def _c2pa_ai_flag(rec, ctx):
    return truthy(rec.get("JUMBF:Ai_generated")) or truthy(rec.get("XMP:AiGenerated"))


def _known_generator_software(rec, ctx):
    return match_vendor(text(rec, *SOFTWARE_FIELDS)) is not None


DIFFUSION_RE = re.compile(
    r"(steps:\s*\d+|sampler:|cfg\s*scale|denoising strength|"
    r"\"class_type\"|negative prompt|seed:\s*-?\d+)", re.I)


def _diffusion_params(rec, ctx):
    blob = text(rec, *PROMPT_FIELDS)
    return bool(blob) and bool(DIFFUSION_RE.search(blob))


# -- tier 2: structural artifacts --------------------------------------------

def _chunk_after_idat(rec, ctx):
    return "after png idat" in text(rec, "ExifTool:Warning")


def _c2pa_present_only(rec, ctx):
    """A signed C2PA manifest that does NOT declare trained-algorithmic media."""
    has = any(k.startswith("JUMBF:") for k in rec)
    return has and not _c2pa_trained(rec, ctx) and not _c2pa_ai_flag(rec, ctx)


# -- tier 3: resolution fingerprint ------------------------------------------

def _size_proven(rec, ctx):
    size = val(rec, "Composite:ImageSize")
    if size is None or size in COMMON_CAPTURE_SIZES:
        return False
    return size in ctx.get("proven_sizes", ())


def _size_native(rec, ctx):
    return val(rec, "Composite:ImageSize") in NATIVE_IMAGE_SIZES


def _video_size_native(rec, ctx):
    return val(rec, "Composite:ImageSize") in NATIVE_VIDEO_SIZES


# -- tier 4: absence signals --------------------------------------------------

CAMERA_TAGS = ("EXIF:Make", "EXIF:Model", "EXIF:ExposureTime", "EXIF:FNumber",
               "EXIF:ISO", "EXIF:DateTimeOriginal", "EXIF:FocalLength")

VIDEO_CAMERA_TAGS = ("QuickTime:Make", "QuickTime:Model", "QuickTime:GPSCoordinates",
                     "QuickTime:CameraIdentifier", "QuickTime:AndroidVersion",
                     "QuickTime:CreationDate", "XMP:Make", "XMP:Model")


def _no_camera_exif(rec, ctx):
    return all(val(rec, t) is None for t in CAMERA_TAGS)


def _no_thumbnail(rec, ctx):
    return val(rec, "EXIF:ThumbnailLength") is None


def _no_camera_video(rec, ctx):
    return all(val(rec, t) is None for t in VIDEO_CAMERA_TAGS)


def _no_audio_track(rec, ctx):
    return val(rec, "QuickTime:AudioFormat") is None and val(rec, "Composite:AudioBitrate") is None


def _short_clip(rec, ctx):
    secs = ctx.get("duration_seconds")
    return secs is not None and 0 < secs <= 12


def _zeroed_timestamps(rec, ctx):
    stamps = [rec.get(t) for t in ("QuickTime:CreateDate", "QuickTime:MediaCreateDate",
                                   "QuickTime:TrackCreateDate")]
    present = [str(s) for s in stamps if s]
    return bool(present) and all(s.startswith("0000:00:00") for s in present)


# -- tier 5: editing provenance ----------------------------------------------

def _photoshop_web(rec, ctx):
    return "photoshop web" in text(rec, "EXIF:Software", "XMP:CreatorTool")


def _edited_generatively(rec, ctx):
    blob = text(rec, "JUMBF:ActionsAction", "XMP:HistoryAction")
    return "generativefill" in blob or ("c2pa.edited" in blob and "generat" in blob)


def _bytedance_app(rec, ctx):
    return val(rec, "QuickTime:LvMetaInfo") is not None


EDITOR_RE = re.compile(
    r"clipchamp|adobe premiere|final cut|davinci resolve|filmora|camtasia|"
    r"kdenlive|shotcut|vegas pro|imovie|inshot|kinemaster|capcut", re.I)

IMAGE_EDITOR_RE = re.compile(
    r"photoshop|lightroom|\bgimp\b|affinity photo|paint\.net|pixelmator|"
    r"luminar|capture one|snapseed", re.I)


def _video_editor(rec, ctx):
    return bool(EDITOR_RE.search(text(rec, *SOFTWARE_FIELDS)))


def _image_editor(rec, ctx):
    blob = text(rec, *SOFTWARE_FIELDS)
    return bool(IMAGE_EDITOR_RE.search(blob)) and "photoshop web" not in blob


# -- provenance reset: why an absence of evidence may mean nothing ------------

def _screen_recording(rec, ctx):
    blob = text(rec, "QuickTime:Author", "QuickTime:HandlerDescription",
                "QuickTime:Title", "QuickTime:Encoder")
    return "replaykit" in blob or "screen record" in blob or "screenrecord" in blob


def _apple_photos(rec, ctx):
    return val(rec, "QuickTime:ApplePhotosOriginatingSignature") is not None


FFMPEG_RE = re.compile(r"\blav[fc]\d|\bffmpeg\b|libx26[45]|\blibvpx\b|\bx264\b|\bx265\b", re.I)


def _ffmpeg_reencode(rec, ctx):
    return bool(FFMPEG_RE.search(text(
        rec, "QuickTime:Encoder", "QuickTime:SoftwareVersion", "QuickTime:VendorID",
        "QuickTime:CompressorName", "QuickTime:HandlerDescription", "QuickTime:Comment")))


# --- explainers: which tag matched, and why ---------------------------------


def _first_matching(rec: Record, fields: Iterable[str], rx: re.Pattern, note: str) -> list[dict]:
    out = []
    for f in fields:
        v = rec.get(f)
        if not v:
            continue
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        m = rx.search(s)
        if m:
            out.append(_row(f, v, note=f'{note} "{m.group(0)}"'))
    return out or [_row(f, rec.get(f)) for f in fields if rec.get(f)]


def _x_aigc(rec, ctx):
    d = aigc_label(rec)
    if not d:
        return []
    src = d.get("_field", "AIGC")
    rows = [_row(src, rec.get(src), note=f"Label={d.get('Label')} — 1 means AI-generated")]
    if d.get("ContentProducer"):
        rows.append(_row(f"{src} → ContentProducer", d["ContentProducer"],
                         note=aigc_producer_name(d["ContentProducer"])))
    return rows


def _x_vendor(rec, ctx):
    for f in SOFTWARE_FIELDS:
        v = rec.get(f)
        if not v:
            continue
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        for rx, name in VENDOR_RE:
            m = rx.search(s)
            if m:
                return [_row(f, v, note=f'matched "{m.group(0)}" → {name}')]
    return []


def _x_diffusion(rec, ctx):
    return _first_matching(rec, PROMPT_FIELDS, DIFFUSION_RE, "matched")


def _x_signed(rec, ctx):
    for f in ("QuickTime:Comment", "QuickTime:UserComment", "EXIF:UserComment", "PNG:Comment"):
        v = rec.get(f)
        if isinstance(v, str) and SIGNED_COMMENT_RE.match(v):
            body = v.split(":", 1)[1].strip()
            return [_row(f, v, note=f"opaque base64, {len(body)} chars → "
                                    f"~{len(body) * 3 // 4} bytes of binary")]
    return []


def _x_size_proven(rec, ctx):
    size = val(rec, "Composite:ImageSize")
    peers = ctx.get("proven_size_sources", {}).get(size, [])
    note = "also used by " + ", ".join(peers[:3]) if peers else None
    if peers and len(peers) > 3:
        note += f" and {len(peers) - 3} more in this batch"
    return [_row("Composite:ImageSize", size, note=note)]


def _x_size(rec, ctx):
    return [_row("Composite:ImageSize", val(rec, "Composite:ImageSize"))]


def _x_duration(rec, ctx):
    secs = ctx.get("duration_seconds")
    return [_row("QuickTime:Duration", rec.get("QuickTime:Duration") or f"{secs}s",
                 note=f"{secs:.1f} s — at or under the 12 s threshold" if secs else None)]


def _x_c2pa_present(rec, ctx):
    keys = [k for k in rec if k.startswith("JUMBF:")][:6]
    return [_row(k, rec[k]) for k in keys]


def _x_editor(rec, ctx):
    return _first_matching(rec, SOFTWARE_FIELDS, EDITOR_RE, "matched")


def _x_image_editor(rec, ctx):
    return _first_matching(rec, SOFTWARE_FIELDS, IMAGE_EDITOR_RE, "matched")


def _x_ffmpeg(rec, ctx):
    return _first_matching(rec, (
        "QuickTime:Encoder", "QuickTime:SoftwareVersion", "QuickTime:VendorID",
        "QuickTime:CompressorName", "QuickTime:HandlerDescription"), FFMPEG_RE, "matched")


def _x_screen_rec(rec, ctx):
    return _first_matching(rec, (
        "QuickTime:Author", "QuickTime:HandlerDescription", "QuickTime:Title",
        "QuickTime:Encoder"), re.compile(r"replaykit|screen ?record", re.I), "matched")


SIGNALS: list[Signal] = [
    Signal("aigc_chunk", "AIGC label (Label=1)", 100, 1, "explicit generator watermark", "both",
           "The file carries China's mandatory AIGC label declaring Label=1 — generated content. "
           "Images keep it in a PNG:AIGC text chunk, video in the QuickTime:AIGC atom; the payload "
           "also names the registered producer and propagator.",
           _aigc_chunk, fields=AIGC_FIELDS, explain=_x_aigc),
    Signal("comfyui_workflow", "ComfyUI workflow embedded", 100, 1, "explicit generator watermark", "both",
           "A ComfyUI node graph is stored in the file (Workflow/Prompt). A full export carries the "
           "whole graph; the VideoHelperSuite node leaves only a stub — either way the file came out "
           "of a ComfyUI pipeline.", _comfyui_workflow, fields=WORKFLOW_FIELDS),
    Signal("signed_comment", "Opaque generator signature", 100, 1, "explicit generator watermark", "both",
           "The Comment atom holds a base64 'Signature:' blob — high-entropy binary, typically 144 "
           "bytes. It is neither C2PA nor the AIGC label but a vendor's own provenance token, written "
           "at mux time. Reported in the wild from xAI's Grok video output.", _signed_comment,
           fields=("QuickTime:Comment", "QuickTime:UserComment", "EXIF:UserComment", "PNG:Comment"),
           explain=_x_signed),
    Signal("recraft_sig", "Recraft signature", 100, 1, "explicit generator watermark", "image",
           "A Recraft AI signature chunk written by the Recraft generator.", _recraft_sig,
           fields=("PNG:Recraft_signature",)),
    Signal("c2pa_trained", "C2PA trainedAlgorithmicMedia", 100, 1, "explicit generator watermark", "both",
           "C2PA Content Credentials declare the IPTC digital source type "
           "'trainedAlgorithmicMedia' - the standardised 'a model generated this'.",
           _c2pa_trained,
           fields=("JUMBF:ActionsDigitalSourceType", "XMP:DigitalSourceType",
                   "JUMBF:DigitalSourceType", "IPTC:DigitalSourceType",
                   "JUMBF:Claim_Generator_InfoName")),
    Signal("c2pa_ai_flag", "C2PA AI-generated flag", 100, 1, "explicit generator watermark", "both",
           "The signed C2PA manifest carries an explicit ai_generated=true assertion.",
           _c2pa_ai_flag, fields=("JUMBF:Ai_generated", "XMP:AiGenerated")),
    Signal("generator_software", "Generator named in software tag", 100, 1, "explicit generator watermark", "both",
           "A known generative tool or model names itself in a Software / CreatorTool / Encoder tag.",
           _known_generator_software, fields=SOFTWARE_FIELDS, explain=_x_vendor),
    Signal("diffusion_params", "Diffusion parameters embedded", 100, 1, "explicit generator watermark", "image",
           "Sampler, steps, CFG scale, seed or a ComfyUI workflow graph is stored in the file - "
           "the generation recipe travels with the image.", _diffusion_params,
           fields=PROMPT_FIELDS, explain=_x_diffusion),

    Signal("chunk_after_idat", "Provenance chunk after IDAT", 20, 2, "structural artifact", "image",
           "ExifTool warns a chunk sits after the PNG image data, the structural fingerprint of a "
           "tag appended by a pipeline after the pixels were written.", _chunk_after_idat,
           fields=("ExifTool:Warning",)),
    Signal("c2pa_unsigned_claim", "C2PA manifest without AI claim", 10, 2, "structural artifact", "both",
           "A C2PA manifest is present but stops short of declaring generated media - typical of "
           "an editing or capture claim, worth reading but not proof.", _c2pa_present_only,
           explain=_x_c2pa_present),

    # Signal("size_proven", "Size proven AI in this batch", 40, 3, "resolution fingerprint", "image",
    #        "This exact pixel size is used by files in this same batch that carry an explicit "
    #        "generator declaration.", _size_proven,
    #        fields=("Composite:ImageSize",), explain=_x_size_proven),
    # Signal("size_native", "Latent-native resolution", 1, 3, "resolution fingerprint", "image",
    #        "A canonical SDXL / FLUX / DALL-E 3 output size that cameras do not produce.", _size_native,
    #        fields=("Composite:ImageSize",), explain=_x_size),
    # Signal("video_size_native", "Generation-native frame size", 20, 3, "resolution fingerprint", "video",
    #        "A frame size characteristic of video generators rather than cameras.", _video_size_native,
    #        fields=("Composite:ImageSize",), explain=_x_size),



    Signal("size_proven", "Size proven AI in this batch", 1, 3, "resolution fingerprint", "image",
           "This exact pixel size is used by files in this same batch that carry an explicit "
           "generator declaration.", _size_proven,
           fields=("Composite:ImageSize",), explain=_x_size_proven),
    Signal("size_native", "Latent-native resolution", 1, 3, "resolution fingerprint", "image",
           "A canonical SDXL / FLUX / DALL-E 3 output size that cameras do not produce.", _size_native,
           fields=("Composite:ImageSize",), explain=_x_size),
    Signal("video_size_native", "Generation-native frame size", 1, 3, "resolution fingerprint", "video",
           "A frame size characteristic of video generators rather than cameras.", _video_size_native,
           fields=("Composite:ImageSize",), explain=_x_size),

    Signal("no_camera_exif", "No camera EXIF", 5, 4, "absence signal", "image",
           "Not one of Make, Model, ExposureTime, FNumber, ISO, DateTimeOriginal or FocalLength is "
           "present - no camera ever wrote to this file.", _no_camera_exif, fields=CAMERA_TAGS),
    Signal("no_thumbnail", "No embedded thumbnail", 2, 4, "absence signal", "image",
           "Cameras embed a preview thumbnail; generators generally do not.", _no_thumbnail,
           fields=("EXIF:ThumbnailLength",)),
    Signal("no_camera_video", "No capture metadata", 5, 4, "absence signal", "video",
           "No Make, Model, GPS or capture date - nothing recorded this on a device.", _no_camera_video,
           fields=VIDEO_CAMERA_TAGS),
    Signal("no_audio_track", "No audio track", 8, 4, "absence signal", "video",
           "The container has no audio stream, common for generated clips and rare for camera footage.",
           _no_audio_track, fields=("QuickTime:AudioFormat", "Composite:AudioBitrate")),
    Signal("short_clip", "Very short clip", 5, 4, "absence signal", "video",
           "Duration of 12 seconds or less, matching the fixed output length of current video models.",
           _short_clip, fields=("QuickTime:Duration",), explain=_x_duration),
    Signal("zeroed_timestamps", "Container timestamps zeroed", 2, 4, "absence signal", "video",
           "Every creation date in the container reads 0000:00:00 — no capture time was ever "
           "written. Common to generated and re-muxed files, and never true of camera output.",
           _zeroed_timestamps,
           fields=("QuickTime:CreateDate", "QuickTime:MediaCreateDate", "QuickTime:TrackCreateDate")),

    Signal("photoshop_web", "Photoshop Web", 50, 5, "editing provenance", "both",
           "Saved by Photoshop Web, the browser editor wired to Adobe's generative features.",
           _photoshop_web, fields=("EXIF:Software", "XMP:CreatorTool")),
    Signal("generative_edit", "Generative edit in history", 50, 5, "editing provenance", "both",
           "The edit history records a generative fill or expand action.", _edited_generatively,
           fields=("JUMBF:ActionsAction", "XMP:HistoryAction")),
    Signal("bytedance_app", "CapCut / Dreamina export", 20, 5, "editing provenance", "video",
           "A QuickTime:LvMetaInfo atom — written by ByteDance's editing and generation apps "
           "(CapCut / Jianying / Dreamina). It names the product and whether the export was a "
           "generation or an edit.", _bytedance_app, fields=("QuickTime:LvMetaInfo",)),
    Signal("video_editor", "Video editor", 10, 5, "editing provenance", "video",
           "A consumer video editor put its name in the container. Editing is not generation, "
           "but it means the file is not camera-original.", _video_editor,
           fields=SOFTWARE_FIELDS, explain=_x_editor),
    Signal("image_editor", "Image editor", 10, 5, "editing provenance", "image",
           "Saved by a desktop image editor. Not generation, but the pixels have been through "
           "an editing tool.", _image_editor, fields=SOFTWARE_FIELDS, explain=_x_image_editor),

    Signal("screen_recording", "Screen recording", 0, 6, "provenance reset", "video",
           "Recorded off a screen (iOS ReplayKit or similar). Whatever provenance the original "
           "carried was destroyed by the re-capture — an absence of AI signals here means nothing.",
           _screen_recording, explain=_x_screen_rec),
    Signal("apple_photos", "Passed through Apple Photos", 0, 6, "provenance reset", "video",
           "Carries an Apple Photos originating signature, so the file was exported from the "
           "Photos library rather than delivered as the camera or generator wrote it.", _apple_photos,
           fields=("QuickTime:ApplePhotosOriginatingSignature",)),
    Signal("ffmpeg_reencode", "Re-encoded (FFmpeg/x264)", 0, 6, "provenance reset", "video",
           "Muxed or transcoded by FFmpeg. Re-encoding discards the original container metadata, "
           "so this file cannot be cleared on absence of evidence alone.", _ffmpeg_reencode,
           explain=_x_ffmpeg),
]

SIGNALS_BY_ID = {s.id: s for s in SIGNALS}

# score -> verdict. Boundaries match the original exif_aigc_scan.py thresholds.
VERDICTS = [
    (100, "confirmed"),
    (40, "suspect"),
    (21, "weak"),
    (0, "unknown"),
]


def verdict_for(score: int) -> str:
    for threshold, name in VERDICTS:
        if score >= threshold:
            return name
    return "unknown"


def registry_payload() -> list[dict]:
    """The registry as JSON for the frontend."""
    return [
        {
            "id": s.id, "label": s.label, "weight": s.weight, "tier": s.tier,
            "category": s.category, "modality": s.modality, "description": s.description,
        }
        for s in SIGNALS
    ]
