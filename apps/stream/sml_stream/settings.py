"""Configuration, read once at import. The process environment is scrubbed afterwards.

The legacy long-form detectors start subprocesses with a copy of os.environ, so nothing secret
may stay in it: the shared secret is kept in memory only and everything not on the allow-list
is removed.
"""

from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    """Fill os.environ from the repository .env for values not already set (development)."""
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()
_env = os.environ.get

SHARED_SECRET: str = _env("STREAM_SHARED_SECRET", "")
API_INTERNAL_URL: str = _env("API_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
if not API_INTERNAL_URL.startswith(("http://", "https://")):
    raise RuntimeError("API_INTERNAL_URL must be an http(s) URL")
LONG_VIDEO_ROOT = Path(_env("LONG_VIDEO_ROOT", str(Path.home() / "fakedetector" / "long-video-processor")))
CONDA_ROOT = Path(_env("CONDA_ROOT", str(Path.home() / "anaconda3")))
WORK_DIR = Path(_env("STREAM_WORK_DIR", str(REPO_ROOT / "var" / "stream")))
MAX_BYTES = int(_env("UPLOAD_MAX_VIDEO_BYTES", str(4 * 1024**3)))
CHUNK_BYTES = 4 * 1024 * 1024
PRELOAD_MODEL = _env("STREAM_PRELOAD_MODEL", "1") != "0"
# Seconds a range may exceed what was paid for (container durations are not exact).
RANGE_TOLERANCE = 1.0


def _find_ffmpeg() -> str:
    explicit = _env("STREAM_FFMPEG_BIN", "")
    if explicit:
        return explicit
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = sorted(glob.glob(str(CONDA_ROOT / "envs" / "*" / "bin" / "ffmpeg")))
    candidates += sorted(glob.glob(str(CONDA_ROOT / "envs" / "*" / "lib" / "python3*" / "site-packages"
                                       / "imageio_ffmpeg" / "binaries" / "ffmpeg-linux-*")))
    return candidates[0] if candidates else "ffmpeg"


FFMPEG_BIN = _find_ffmpeg()

# Settings the legacy engine reads from the environment.
os.environ["CONDA_BIN"] = str(CONDA_ROOT / "bin" / "conda")
os.environ["FFMPEG_BIN"] = FFMPEG_BIN
os.environ.setdefault("LONG_FORM_EXTERNAL_WORK_DIR", str(WORK_DIR / "external"))

_ALLOWED = {"HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TZ", "TMPDIR", "TERM", "SHELL", "PATH",
            "CUDA_HOME", "CUDA_PATH", "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "LD_LIBRARY_PATH",
            "PYTORCH_CUDA_ALLOC_CONF", "CONDA_BIN", "FFMPEG_BIN", "PYTHONUNBUFFERED"}
_ALLOWED_PREFIXES = ("LC_", "LONG_FORM_", "BEYBI_", "SKKU_P2_", "SKKU_P3_", "HF_", "TORCH_", "XDG_", "OMP_")


def scrub_environment() -> None:
    for key in list(os.environ):
        if key not in _ALLOWED and not key.startswith(_ALLOWED_PREFIXES):
            del os.environ[key]


scrub_environment()
