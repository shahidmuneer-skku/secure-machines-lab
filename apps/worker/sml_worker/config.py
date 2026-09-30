"""Worker configuration from environment variables (shares the repository .env)."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("DJANGO_"):
            continue  # the worker is Django-free
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class WorkerConfig:
    broker_url: str
    redis_url: str
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    local_media_root: Path
    models_config: Path
    models_root: Path
    long_video_root: Path
    conda_root: Path
    simulate: str  # auto | 1 | 0
    ollama_base_url: str
    openclaude_bin: str
    searxng_url: str
    anthropic_api_key: str
    scratch_root: Path
    hostname: str = field(default_factory=socket.gethostname)

    def conda_python(self, env: str) -> Path:
        return self.conda_root / "envs" / env / "bin" / "python"


def gpu_env() -> dict[str, str]:
    """GPU environment for model subprocesses.

    CUDA's default FASTEST_FIRST ordering would put the RTX PRO 6000 (Blackwell, sm_120)
    at index 0 — legacy envs (torch cu124) have no kernels for it. PCI_BUS_ID makes indices
    match nvidia-smi, and unpinned workers default to SML_WORKER_DEFAULT_GPU (an A5000).
    """
    gpu = os.environ.get("SML_WORKER_GPU") or os.environ.get("SML_WORKER_DEFAULT_GPU", "0")
    return {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": gpu}


@lru_cache(maxsize=1)
def config() -> WorkerConfig:
    _load_dotenv()
    env = os.environ.get
    return WorkerConfig(
        broker_url=env("CELERY_BROKER_URL", "amqp://sml:sml@127.0.0.1:55672/sml"),
        redis_url=env("REDIS_URL", "redis://127.0.0.1:56379/0"),
        s3_endpoint=env("S3_ENDPOINT_URL", ""),
        s3_bucket=env("S3_BUCKET", "sml-media"),
        s3_access_key=env("S3_ACCESS_KEY", ""),
        s3_secret_key=env("S3_SECRET_KEY", ""),
        s3_region=env("S3_REGION", "us-east-1"),
        local_media_root=Path(env("LOCAL_MEDIA_ROOT", str(REPO_ROOT / "var" / "media"))),
        models_config=Path(env("MODELS_CONFIG_PATH", str(REPO_ROOT / "config" / "models.yaml"))),
        models_root=Path(env("MODELS_ROOT", "/models")),
        long_video_root=Path(env("LONG_VIDEO_ROOT", "/models/long-video-processor")),
        conda_root=Path(env("CONDA_ROOT", str(Path.home() / "anaconda3"))),
        simulate=env("SML_WORKER_SIMULATE", "auto"),
        ollama_base_url=env("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        openclaude_bin=env("OPENCLAUDE_BIN", str(Path.home() / "openclaude" / "bin" / "openclaude")),
        searxng_url=env("OPENCLAUDE_SEARXNG_URL", ""),
        anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
        scratch_root=Path(env("SML_WORKER_SCRATCH", "/tmp/sml-worker")),
    )
