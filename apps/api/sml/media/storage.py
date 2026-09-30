"""Object storage helpers. S3/MinIO in dev/prod; local filesystem in tests.

Keys are always server-generated (UUIDs); user file names never reach a path.
"""

from __future__ import annotations

import mimetypes
from functools import lru_cache
from pathlib import Path
from typing import IO, Any

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import storages


def media_storage() -> Any:
    return storages["default"]


def uses_s3() -> bool:
    return bool(settings.S3_ENDPOINT_URL)


@lru_cache(maxsize=2)
def s3_client(public: bool = False) -> Any:
    endpoint = settings.S3_PUBLIC_ENDPOINT_URL if public else settings.S3_ENDPOINT_URL
    return boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY, region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def save_bytes(key: str, data: bytes) -> str:
    return media_storage().save(key, ContentFile(data))


def save_file(key: str, fh: IO[bytes]) -> str:
    return media_storage().save(key, File(fh))


def open_file(key: str) -> IO[bytes]:
    return media_storage().open(key, "rb")


def delete(key: str) -> None:
    if key:
        media_storage().delete(key)


def local_path(key: str) -> Path | None:
    """Filesystem path when using local storage (tests/dev without MinIO)."""
    if uses_s3():
        return None
    return Path(media_storage().path(key))


def presigned_get(key: str, *, filename: str | None = None, expires: int = 300, inline: bool = True) -> str:
    params: dict[str, Any] = {"Bucket": settings.S3_BUCKET, "Key": key}
    content_type = mimetypes.guess_type(key)[0]
    if content_type:
        params["ResponseContentType"] = content_type
    if filename:
        disposition = "inline" if inline else "attachment"
        safe = filename.replace('"', "").encode("ascii", "ignore").decode() or "file"
        params["ResponseContentDisposition"] = f'{disposition}; filename="{safe}"'
    return s3_client(public=True).generate_presigned_url("get_object", Params=params, ExpiresIn=expires)


# --- multipart (large videos, resumable) ----------------------------------------

PART_SIZE = 64 * 1024 * 1024


def multipart_create(key: str, content_type: str) -> str:
    resp = s3_client().create_multipart_upload(Bucket=settings.S3_BUCKET, Key=key, ContentType=content_type)
    return resp["UploadId"]


def multipart_part_urls(key: str, upload_id: str, parts: int, expires: int = 3600) -> list[str]:
    client = s3_client(public=True)
    return [
        client.generate_presigned_url(
            "upload_part",
            Params={"Bucket": settings.S3_BUCKET, "Key": key, "UploadId": upload_id, "PartNumber": n},
            ExpiresIn=expires,
        )
        for n in range(1, parts + 1)
    ]


def multipart_complete(key: str, upload_id: str, parts: list[dict[str, Any]]) -> None:
    s3_client().complete_multipart_upload(
        Bucket=settings.S3_BUCKET, Key=key, UploadId=upload_id,
        MultipartUpload={"Parts": [{"PartNumber": int(p["part_number"]), "ETag": p["etag"]} for p in parts]},
    )


def multipart_abort(key: str, upload_id: str) -> None:
    s3_client().abort_multipart_upload(Bucket=settings.S3_BUCKET, Key=key, UploadId=upload_id)


def download_to(key: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if uses_s3():
        s3_client().download_file(settings.S3_BUCKET, key, str(dest))
    else:
        with open_file(key) as src, dest.open("wb") as out:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                out.write(chunk)
    return dest
