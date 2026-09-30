"""Reports scan progress to the Django API (internal endpoint, shared-secret header)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from . import settings

logger = logging.getLogger(__name__)


class ApiRefused(Exception):
    """The API rejected the report (e.g. the job was canceled); the scan must stop."""


def report(session_id: str, event: str, payload: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
    url = f"{settings.API_INTERNAL_URL}/api/internal/streams/{session_id}/events"
    body = json.dumps({"event": event, **payload}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, method="POST", headers={  # noqa: S310 - http(s) only (settings)
            "Content-Type": "application/json", "X-Stream-Key": settings.SHARED_SECRET})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - internal URL from settings
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 403, 404, 409):
                raise ApiRefused(f"API refused {event}: HTTP {exc.code}") from exc
            logger.warning("Report %s for %s failed (HTTP %s), attempt %s", event, session_id, exc.code, attempt + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("Report %s for %s failed (%s), attempt %s", event, session_id, exc, attempt + 1)
        time.sleep(1.5 * (attempt + 1))
    raise ConnectionError(f"Could not report {event} for stream {session_id}")
