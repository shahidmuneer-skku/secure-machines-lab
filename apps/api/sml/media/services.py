"""Upload ingestion: verify, store under a random key, thumbnail, record."""

from __future__ import annotations

import math
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import IO, Any

from django.conf import settings
from django.utils import timezone

from sml.core.exceptions import ApiError, InvalidMedia
from sml.core.ids import uuid7

from . import storage
from .models import MediaObject
from .validation import probe_file, sniff

MAX_NAME = 255


def _clean_name(name: str) -> str:
    name = Path(name or "upload").name.strip() or "upload"
    return name[:MAX_NAME]


def _owner_prefix(owner: Any, guest_token: str) -> str:
    return f"u/{owner.pk}" if owner is not None else f"g/{guest_token[:16]}"


def _consent(owner: Any) -> bool:
    consent = getattr(owner, "training_consent", None) if owner is not None else None
    return bool(consent and consent.granted)


def _retention_expiry(owner: Any) -> Any:
    from sml.jobs.retention import retention_days_for

    return timezone.now() + timedelta(days=retention_days_for(owner))


def ingest_file(fh: IO[bytes], *, original_name: str, owner: Any = None, guest_token: str = "") -> MediaObject:
    """Verify an uploaded file stream and persist it. Raises InvalidMedia."""
    with tempfile.TemporaryDirectory(prefix="sml-upload-") as tmp:
        tmp_path = Path(tmp) / "upload.bin"
        with tmp_path.open("wb") as out:
            shutil.copyfileobj(fh, out, 1024 * 1024)
        probe = probe_file(tmp_path)
        media_id = uuid7()
        key = f"media/{_owner_prefix(owner, guest_token)}/{media_id}.{probe.extension}"
        with tmp_path.open("rb") as src:
            stored_key = storage.save_file(key, src)
        thumb_key = ""
        from .validation import make_thumbnail

        thumb = make_thumbnail(tmp_path, probe.media_type)
        if thumb:
            thumb_key = storage.save_bytes(f"thumbs/{_owner_prefix(owner, guest_token)}/{media_id}.jpg", thumb)
    return MediaObject.objects.create(
        id=media_id, owner=owner, guest_token=guest_token, status=MediaObject.Status.READY,
        media_type=probe.media_type, original_name=_clean_name(original_name), extension=probe.extension,
        content_type=probe.content_type, size_bytes=probe.size_bytes, sha256=probe.sha256,
        storage_key=stored_key, thumbnail_key=thumb_key, width=probe.width, height=probe.height,
        duration_seconds=probe.duration_seconds, fps=probe.fps, frame_count=probe.frame_count,
        codec=probe.codec, training_consent=_consent(owner), expires_at=_retention_expiry(owner),
    )


# --- presigned multipart upload (browser → MinIO/S3 directly) --------------------

def start_multipart(*, owner: Any, original_name: str, size_bytes: int, head: bytes) -> tuple[MediaObject, list[str]]:
    if not storage.uses_s3():
        raise ApiError("Direct uploads require object storage; use POST /uploads instead.")
    media_type, mime, ext = sniff(head)
    if media_type != "video":
        raise InvalidMedia("Multipart uploads are for videos; upload images with POST /uploads.")
    if size_bytes <= 0 or size_bytes > settings.UPLOAD_MAX_VIDEO_BYTES:
        raise InvalidMedia(f"Video too large. Limit is {settings.UPLOAD_MAX_VIDEO_BYTES // (1024 * 1024)} MB.")
    media_id = uuid7()
    key = f"media/{_owner_prefix(owner, '')}/{media_id}.{ext}"
    upload_id = storage.multipart_create(key, mime)
    parts = max(1, math.ceil(size_bytes / storage.PART_SIZE))
    media = MediaObject.objects.create(
        id=media_id, owner=owner, status=MediaObject.Status.UPLOADING, media_type=media_type,
        original_name=_clean_name(original_name), extension=ext, content_type=mime, size_bytes=size_bytes,
        storage_key=key, s3_multipart_upload_id=upload_id, training_consent=_consent(owner),
        expires_at=_retention_expiry(owner),
    )
    return media, storage.multipart_part_urls(key, upload_id, parts)


def complete_multipart(media: MediaObject, parts: list[dict[str, Any]]) -> MediaObject:
    if media.status != MediaObject.Status.UPLOADING:
        raise ApiError("This upload is already completed.")
    storage.multipart_complete(media.storage_key, media.s3_multipart_upload_id, parts)
    with tempfile.TemporaryDirectory(prefix="sml-verify-") as tmp:
        local = storage.download_to(media.storage_key, Path(tmp) / f"verify.{media.extension}")
        try:
            probe = probe_file(local)
        except InvalidMedia as exc:
            storage.delete(media.storage_key)
            media.status = MediaObject.Status.REJECTED
            media.rejection_reason = str(exc.detail)[:255]
            media.save(update_fields=["status", "rejection_reason", "updated_at"])
            raise
        from .validation import make_thumbnail

        thumb = make_thumbnail(local, probe.media_type)
    media.status = MediaObject.Status.READY
    media.sha256 = probe.sha256
    media.size_bytes = probe.size_bytes
    media.width, media.height = probe.width, probe.height
    media.duration_seconds, media.fps = probe.duration_seconds, probe.fps
    media.frame_count, media.codec = probe.frame_count, probe.codec
    if thumb:
        media.thumbnail_key = storage.save_bytes(f"thumbs/u/{media.owner_id}/{media.pk}.jpg", thumb)
    media.save()
    return media


def purge(media: MediaObject) -> None:
    storage.delete(media.storage_key)
    storage.delete(media.thumbnail_key)
    media.status = MediaObject.Status.DELETED
    media.deleted_at = timezone.now()
    media.save(update_fields=["status", "deleted_at", "updated_at"])
