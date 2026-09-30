"""Stream tokens: issued by the Django API when a scan is paid for, verified here.

Format: base64url(JSON claims) + "." + hex HMAC-SHA256 of that part, keyed with
STREAM_SHARED_SECRET. The claims fix everything that was paid for (model, range, file size),
so the browser cannot change them after the credits were reserved.
(The API side lives in apps/api/sml/jobs/streams.py; keep both in sync.)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class TokenError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(claims: dict[str, Any], secret: str) -> str:
    body = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify(token: str, secret: str, now: float | None = None) -> dict[str, Any]:
    if not secret:
        raise TokenError("The stream service has no shared secret configured.")
    try:
        body, mac = token.rsplit(".", 1)
    except (AttributeError, ValueError) as exc:
        raise TokenError("Malformed token.") from exc
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        raise TokenError("Invalid token.")
    try:
        claims = json.loads(_unb64(body))
    except ValueError as exc:
        raise TokenError("Malformed token.") from exc
    if float(claims.get("exp", 0)) < (now if now is not None else time.time()):
        raise TokenError("This stream link has expired. Start the scan again.")
    return claims
