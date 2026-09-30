"""Runs a stand-in model script through the real SubprocessAdapter (no GPU needed)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from sml_worker.adapters.base import AdapterError
from sml_worker.adapters.subprocess_cli import SubprocessAdapter

MODEL = {"id": "fake-model", "family": "deepfake", "display_name": {"en": "Fake"}, "face_required": True}


def write_script(models: Path, body: str) -> None:
    (models / "fake_model.py").write_text(textwrap.dedent(body))


def adapter(timeout: int = 30) -> SubprocessAdapter:
    spec = {"conda_env": "fake", "argv": ["{python}", "fake_model.py", "{input}", "{page_type}"],
            "cwd": "{models_root}", "parser": "standard"}
    return SubprocessAdapter(MODEL, spec, timeout)


@pytest.fixture
def image(tmp_path: Path) -> Path:
    p = tmp_path / "in.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    return p


def test_success_scrubs_secrets_pins_gpu_and_collects_artifacts(worker_env, ctx_factory, image, uploads):
    write_script(worker_env["models"], """
        import os, sys, pathlib
        stem = pathlib.Path(sys.argv[1]).stem
        out = pathlib.Path("inference_images"); out.mkdir(exist_ok=True)
        (out / f"{stem}_gradcam.png").write_bytes(b"png")
        assert "DJANGO_SECRET_KEY" not in os.environ and "STRIPE_SECRET_KEY" not in os.environ
        assert os.environ["CUDA_VISIBLE_DEVICES"] == "0" and os.environ["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
        assert sys.argv[2] == "deepfake-image"
        print("Loading model"); print("Fake Prob: 0.83")
    """)
    ctx = ctx_factory()
    result = adapter().run(image, "image", ctx)
    assert result.fake_prob == pytest.approx(0.83)
    assert [a.label for a in ctx.artifacts] == ["Grad-CAM"]
    assert not list((worker_env["models"] / "inference_images").iterdir()), "legacy outputs are cleaned up"


def test_no_face_exit_is_a_result_not_an_error(worker_env, ctx_factory, image):
    write_script(worker_env["models"], """
        import sys
        print("No faces detected", file=sys.stderr); sys.exit(1)
    """)
    assert adapter().run(image, "image", ctx_factory()).no_face


@pytest.mark.parametrize(("stderr", "code"), [
    ("torch.cuda.OutOfMemoryError: CUDA out of memory", "GPU_OOM"),
    ("RuntimeError: CUDA error: no kernel image is available for execution on the device", "GPU_UNSUPPORTED"),
    ("ValueError: bad", "RUNTIME_ERROR"),
])
def test_failures_are_classified(worker_env, ctx_factory, image, stderr, code):
    write_script(worker_env["models"], f"""
        import sys
        print({stderr!r}, file=sys.stderr); sys.exit(1)
    """)
    with pytest.raises(AdapterError) as exc:
        adapter().run(image, "image", ctx_factory())
    assert exc.value.code == code


def test_missing_score_is_a_parse_error(worker_env, ctx_factory, image):
    write_script(worker_env["models"], "print('done')\n")
    with pytest.raises(AdapterError) as exc:
        adapter().run(image, "image", ctx_factory())
    assert exc.value.code == "PARSE_ERROR"


def test_timeout_kills_the_process_group(worker_env, ctx_factory, image):
    write_script(worker_env["models"], "import time\ntime.sleep(60)\n")
    with pytest.raises(AdapterError) as exc:
        adapter(timeout=2).run(image, "image", ctx_factory())
    assert exc.value.code == "TIMEOUT"


def test_explicit_worker_gpu_wins(worker_env, monkeypatch):
    from sml_worker.config import gpu_env

    assert gpu_env()["CUDA_VISIBLE_DEVICES"] == "0"
    monkeypatch.setenv("SML_WORKER_GPU", "3")
    assert gpu_env() == {"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": "3"}


@pytest.mark.parametrize(("line", "expected"), [
    ("Loading weights from /home/user/models/xception/best.pt", "Loading weights from …/best.pt"),
    ('File "/opt/conda/envs/x/lib/python3.7/site-packages/dlib/__init__.py", line 19',
     'File "…/__init__.py", line 19'),
    ("Sources: https://example.com/news/a/b and http://x.org/y/z", "Sources: https://example.com/news/a/b and http://x.org/y/z"),
    ("Processed 1/2 frames at 3/4 speed", "Processed 1/2 frames at 3/4 speed"),
    ("Face detected", "Face detected"),
])
def test_live_log_lines_hide_server_paths(line, expected):
    from sml_worker.context import redact_paths

    assert redact_paths(line) == expected


def test_failures_show_only_the_code_in_the_live_log(worker_env, ctx_factory, image):
    write_script(worker_env["models"], """
        import sys
        print('Traceback: /home/secret/env/lib/python3.7/site-packages/dlib/__init__.py', file=sys.stderr); sys.exit(1)
    """)
    ctx = ctx_factory()
    logged: list[str] = []
    ctx.log = logged.append  # type: ignore[method-assign]
    from sml_worker.adapters.base import AdapterError

    with pytest.raises(AdapterError) as exc:
        adapter().run(image, "image", ctx)
    assert "/home/secret" in exc.value.message  # kept for staff (error_detail)
    assert not any("/home/secret" in line for line in logged)


def test_model_env_is_activated_allow_listed_and_extended(worker_env, monkeypatch):
    import os

    from sml_worker import procenv

    monkeypatch.setenv("DATABASE_URL", "postgres://secret")
    monkeypatch.setenv("CELERY_BROKER_URL", "amqp://secret")
    monkeypatch.setenv("EMAIL_HOST_PASSWORD", "secret")
    monkeypatch.setenv("HF_HOME", "/data/hf")
    monkeypatch.setattr(procenv, "conda_env_extras",
                        lambda name: {"LD_LIBRARY_PATH": "{env_prefix}/lib"} if name == "fake" else {})
    env = procenv.model_env("fake")
    prefix = str(worker_env["tmp"] / "conda" / "envs" / "fake")
    assert env["PATH"].split(os.pathsep)[0] == f"{prefix}/bin"
    assert env["CONDA_PREFIX"] == prefix and env["CONDA_DEFAULT_ENV"] == "fake"
    assert env["LD_LIBRARY_PATH"].split(os.pathsep)[0] == f"{prefix}/lib"
    assert env["HF_HOME"] == "/data/hf" and env["CUDA_VISIBLE_DEVICES"] == "0"
    leaked = {k for k in env if k.startswith(("DJANGO_", "STRIPE_", "DATABASE", "CELERY", "EMAIL", "REDIS", "S3_"))}
    assert not leaked


def test_bare_python_in_model_scripts_resolves_to_the_env(worker_env, ctx_factory, image):
    write_script(worker_env["models"], """
        import subprocess, sys
        child = subprocess.run(["python", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True)
        assert "envs/fake/bin" in child.stdout, child.stdout
        print("Fake Prob: 0.5")
    """)
    assert adapter().run(image, "image", ctx_factory()).fake_prob == pytest.approx(0.5)
