"""Redis and object-storage clients."""

from __future__ import annotations

import mimetypes
import shutil
from functools import lru_cache
from pathlib import Path

import boto3
import redis
from botocore.config import Config

from .config import config


@lru_cache(maxsize=1)
def redis_client() -> redis.Redis:
    return redis.Redis.from_url(config().redis_url)


@lru_cache(maxsize=1)
def _s3():  # type: ignore[no-untyped-def]
    c = config()
    return boto3.client("s3", endpoint_url=c.s3_endpoint, aws_access_key_id=c.s3_access_key,
                        aws_secret_access_key=c.s3_secret_key, region_name=c.s3_region,
                        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))


def download(key: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    c = config()
    if c.s3_endpoint:
        _s3().download_file(c.s3_bucket, key, str(dest))
    else:
        shutil.copyfile(c.local_media_root / key, dest)
    return dest


def upload(path: Path, key: str) -> tuple[str, str, int]:
    """Uploads an artifact; returns (key, content_type, size)."""
    c = config()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    size = path.stat().st_size
    if c.s3_endpoint:
        _s3().upload_file(str(path), c.s3_bucket, key, ExtraArgs={"ContentType": content_type})
    else:
        target = c.local_media_root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return key, content_type, size
