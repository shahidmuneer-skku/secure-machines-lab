"""Server-side verification of uploads: magic bytes, decodability, limits.

The declared extension/content type is never trusted: the media type is derived
from the file signature, then confirmed by actually decoding the file.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import av
import filetype
from django.conf import settings
from PIL import Image, ImageOps

from sml.core.exceptions import InvalidMedia

IMAGE_TYPES = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/bmp": "bmp", "image/avif": "avif",
}
VIDEO_TYPES = {
    "video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov", "video/x-msvideo": "avi",
    "video/x-matroska": "mkv", "image/gif": "gif",
}
ACCEPT_EXTENSIONS = sorted({*IMAGE_TYPES.values(), "jpeg", *VIDEO_TYPES.values()})

Image.MAX_IMAGE_PIXELS = settings.UPLOAD_MAX_IMAGE_PIXELS


@dataclass
class ProbeResult:
    media_type: str
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    fps: float | None = None
    frame_count: int | None = None
    codec: str = ""


def sniff(head: bytes) -> tuple[str, str, str]:
    kind = filetype.guess(head)
    if kind is None:
        raise InvalidMedia("Unrecognized file type. Supported: " + ", ".join(ACCEPT_EXTENSIONS))
    mime = kind.mime
    if mime in IMAGE_TYPES:
        return "image", mime, IMAGE_TYPES[mime]
    if mime in VIDEO_TYPES:
        # Animated GIFs are treated as video (legacy behavior).
        return "video", mime, VIDEO_TYPES[mime]
    raise InvalidMedia(f"Unsupported file type ({mime}). Supported: " + ", ".join(ACCEPT_EXTENSIONS))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_file(path: Path) -> ProbeResult:
    size = path.stat().st_size
    if size == 0:
        raise InvalidMedia("The file is empty.")
    with path.open("rb") as fh:
        head = fh.read(8192)
    media_type, mime, ext = sniff(head)
    limit = settings.UPLOAD_MAX_IMAGE_BYTES if media_type == "image" else settings.UPLOAD_MAX_VIDEO_BYTES
    if size > limit:
        raise InvalidMedia(f"File too large ({size // (1024 * 1024)} MB). Limit is {limit // (1024 * 1024)} MB.")
    result = ProbeResult(media_type, mime, ext, size, sha256_file(path))
    if media_type == "image":
        _probe_image(path, result)
    else:
        _probe_video(path, result)
    return result


def _probe_image(path: Path, result: ProbeResult) -> None:
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            result.width, result.height = img.size
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidMedia("Image resolution is too large.") from exc
    except Exception as exc:  # any decoder error means the file is not a valid image
        raise InvalidMedia("The image could not be decoded.") from exc


def _probe_video(path: Path, result: ProbeResult) -> None:
    try:
        with av.open(str(path)) as container:
            stream = next((s for s in container.streams if s.type == "video"), None)
            if stream is None:
                raise InvalidMedia("The file has no video stream.")
            duration = None
            if container.duration:
                duration = container.duration / 1_000_000
            elif stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            result.duration_seconds = round(duration, 3) if duration else None
            result.width = stream.codec_context.width or None
            result.height = stream.codec_context.height or None
            rate = stream.average_rate or stream.base_rate
            result.fps = round(float(rate), 3) if rate else None
            result.frame_count = int(stream.frames) if stream.frames else None
            result.codec = (stream.codec_context.name or "")[:32]
    except InvalidMedia:
        raise
    except Exception as exc:
        raise InvalidMedia("The video could not be decoded.") from exc
    if result.duration_seconds and result.duration_seconds > settings.UPLOAD_MAX_VIDEO_SECONDS:
        raise InvalidMedia(f"Video is too long (max {settings.UPLOAD_MAX_VIDEO_SECONDS // 60} minutes).")


def make_thumbnail(path: Path, media_type: str, max_side: int = 640) -> bytes | None:
    """JPEG thumbnail with all metadata stripped (originals are kept separately for analysis)."""
    try:
        if media_type == "image":
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                frame = img.convert("RGB")
        else:
            with av.open(str(path)) as container:
                stream = container.streams.video[0]
                stream.codec_context.skip_frame = "NONKEY"
                frame = next(container.decode(stream)).to_image().convert("RGB")
        frame.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        frame.save(buf, "JPEG", quality=82, optimize=True)
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - thumbnails are best effort
        return None
