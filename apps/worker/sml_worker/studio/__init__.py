"""Image studio: generation and instruction-based editing (config/studio.yaml, owner 2026-10-01).

* `server.py` runs in the `imagegen` conda env on the studio GPU and keeps the admin's models loaded;
  the resident supervisor starts and restarts it (`python -m sml_worker --resident`).
* `task.py` runs a studio job on a worker (`python -m sml_worker --studio`): prompt check, reference
  checks (faces need consent, NSFW is refused), generation on the server, upload of the outputs.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import REPO_ROOT, config

QUEUE = "sml.studio"
KEEP_KEY = "sml:studio:keep"  # the admin's models, in order (written by the API)
SERVER_ID = "studio"


def config_path() -> Path:
    return Path(os.environ.get("STUDIO_CONFIG_PATH") or REPO_ROOT / "config" / "studio.yaml")


@lru_cache(maxsize=1)
def studio_config() -> dict[str, Any]:
    path = config_path()
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def model(model_id: str) -> dict[str, Any] | None:
    return next((m for m in studio_config().get("models", []) if m["id"] == model_id), None)


def server_config(socket_path: str, keep: list[str]) -> dict[str, Any]:
    """The JSON the studio server starts with (paths resolved, the admin's models to keep loaded)."""
    raw = studio_config()
    root = config().models_root
    safety = {k: (os.path.expanduser(v.format(models_root=root)) if isinstance(v, str) else v)
              for k, v in (raw.get("safety") or {}).items()}
    return {"socket": socket_path, "models": raw.get("models", []), "keep": keep, "safety": safety,
            **(raw.get("server") or {})}


def parse_keep(raw: bytes | str | None) -> list[str]:
    try:
        value = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return [str(m) for m in value] if isinstance(value, list) else []
