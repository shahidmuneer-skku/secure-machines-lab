"""Worker tests run without Redis, S3 or GPUs: the context's clients are replaced with fakes."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
import redis


@pytest.fixture
def worker_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """A models root and a fake conda env whose python is this interpreter."""
    models = tmp_path / "models"
    models.mkdir()
    env_bin = tmp_path / "conda" / "envs" / "fake" / "bin"
    env_bin.mkdir(parents=True)
    os.symlink(sys.executable, env_bin / "python")
    monkeypatch.setenv("MODELS_ROOT", str(models))
    monkeypatch.setenv("CONDA_ROOT", str(tmp_path / "conda"))
    monkeypatch.setenv("SML_WORKER_DEFAULT_GPU", "0")
    monkeypatch.delenv("SML_WORKER_GPU", raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY", "must-not-leak")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "must-not-leak")

    from sml_worker import config as cfg

    cfg.config.cache_clear()
    yield {"models": models, "tmp": tmp_path}
    cfg.config.cache_clear()


@pytest.fixture
def uploads(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    def fake_upload(path: Path, key: str) -> tuple[str, str, int]:
        sent.append((path.name, key))
        return key, "image/png", path.stat().st_size

    def no_redis() -> Any:
        raise redis.RedisError("not in tests")

    monkeypatch.setattr("sml_worker.context.upload", fake_upload)
    monkeypatch.setattr("sml_worker.context.redis_client", no_redis)
    return sent


@pytest.fixture
def ctx_factory(tmp_path: Path, uploads):  # type: ignore[no-untyped-def]
    from sml_worker.context import TaskContext

    def make(task_id: str = "0190aaaa-bbbb-7ccc-8ddd-eeeeffff0000") -> TaskContext:
        workdir = tmp_path / "work" / task_id
        workdir.mkdir(parents=True)
        envelope = {"task_id": task_id, "job_id": "job-1", "user_id": "user-1",
                    "media": {"original_name": "홍길동 photo.png"}, "options": {}}
        return TaskContext(envelope, workdir, gpu="0")

    return make
