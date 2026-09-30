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
