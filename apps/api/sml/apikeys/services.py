from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import ApiKey, ApiKeyUsageDaily

KEY_RE = re.compile(r"^sml_(?:live|test)_([a-z0-9]{12})_([A-Za-z0-9_-]{32,64})$")
MAX_KEYS_PER_USER = 25


def _hash(secret: str) -> str:
    return hmac.new(settings.API_KEY_PEPPER.encode(), secret.encode(), hashlib.sha256).hexdigest()


@dataclass
class IssuedKey:
    api_key: ApiKey
    plaintext: str


def issue_key(
    user: Any,
    *,
    name: str,
    scopes: list[str],
    allowed_ips: list[str] | None = None,
    rate_limit_per_minute: int | None = None,
    expires_at: datetime | None = None,
    rotated_from: ApiKey | None = None,
) -> IssuedKey:
    prefix = secrets.token_hex(6)  # 12 lowercase hex chars
    secret = secrets.token_urlsafe(32)
    key = ApiKey.objects.create(
        user=user, name=name, prefix=prefix, secret_hash=_hash(secret), last_four=secret[-4:],
        scopes=sorted(set(scopes)), allowed_ips=allowed_ips or [],
        rate_limit_per_minute=rate_limit_per_minute, expires_at=expires_at, rotated_from=rotated_from,
    )
    return IssuedKey(key, f"sml_{settings.API_KEY_ENV_LABEL}_{prefix}_{secret}")


def verify(raw: str) -> ApiKey | None:
    """Returns the active key for a presented secret, or None. Constant-time comparison."""
    m = KEY_RE.match(raw.strip())
    if not m:
        return None
    prefix, secret = m.groups()
    key = ApiKey.objects.select_related("user").filter(prefix=prefix).first()
    if key is None:
        _hash(secret)  # keep timing similar for unknown prefixes
        return None
    if not hmac.compare_digest(key.secret_hash, _hash(secret)):
        return None
    if key.status != "active":
        return None
    return key


def revoke(key: ApiKey) -> ApiKey:
    if not key.revoked_at:
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at", "updated_at"])
    return key


@transaction.atomic
def rotate(key: ApiKey) -> IssuedKey:
    """Issue a replacement with identical settings and revoke the old key."""
    issued = issue_key(
        key.user, name=key.name, scopes=key.scopes, allowed_ips=key.allowed_ips,
        rate_limit_per_minute=key.rate_limit_per_minute,
        expires_at=key.expires_at, rotated_from=key,
    )
    revoke(key)
    return issued


def bump_usage(key: ApiKey, *, requests: int = 0, errors: int = 0, jobs: int = 0, credits: int = 0) -> None:
    today = timezone.localdate()
    row, _ = ApiKeyUsageDaily.objects.get_or_create(api_key=key, date=today)
    ApiKeyUsageDaily.objects.filter(pk=row.pk).update(
        requests=F("requests") + requests, errors=F("errors") + errors,
        jobs_created=F("jobs_created") + jobs, credits_spent=F("credits_spent") + credits,
    )
