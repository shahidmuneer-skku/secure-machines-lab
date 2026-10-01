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


def test_relocated_envs_get_their_own_ca_certificates(worker_env, monkeypatch):
    from sml_worker import procenv

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    assert "SSL_CERT_FILE" not in procenv.model_env("fake")  # env without a bundle: leave OpenSSL's default
    certs = worker_env["tmp"] / "conda" / "envs" / "fake" / "ssl" / "cacert.pem"
    certs.parent.mkdir()
    certs.write_text("-----BEGIN CERTIFICATE-----\n")
    assert procenv.model_env("fake")["SSL_CERT_FILE"] == str(certs)


def test_a_worker_shutdown_stops_the_model_and_requeues_the_task(worker_env, ctx_factory, image, monkeypatch, tmp_path):
    """A restart signals the pool processes: the model must not keep running (and holding the GPU)
    on its own, and the task must go back to the queue instead of being acknowledged as failed."""
    import time as real_time

    from celery.exceptions import Reject

    from sml_worker import app as worker_app
    from sml_worker.adapters import subprocess_cli

    pidfile = tmp_path / "model.pid"
    write_script(worker_env["models"], f"import os, time\nopen({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
                                       "time.sleep(60)\n")
    original_sleep = real_time.sleep

    def sleep(seconds):  # type: ignore[no-untyped-def]
        if pidfile.exists():  # the worker receives SIGTERM while the model runs
            raise SystemExit(-15)
        original_sleep(seconds)

    monkeypatch.setattr(subprocess_cli.time, "sleep", sleep)
    with pytest.raises(SystemExit):
        adapter(timeout=30).run(image, "image", ctx_factory())
    pid = int(pidfile.read_text())

    def stopped() -> bool:  # gone, or a zombie waiting to be reaped (it holds no GPU memory)
        status = Path(f"/proc/{pid}/status")
        return not status.exists() or "State:\tZ" in status.read_text()

    deadline = real_time.monotonic() + 5
    while not stopped() and real_time.monotonic() < deadline:
        original_sleep(0.1)
    assert stopped(), "the model process outlived the worker"

    def shutdown(app, envelope):  # type: ignore[no-untyped-def]
        raise SystemExit(-15)

    monkeypatch.setattr("sml_worker.runner.run_envelope", shutdown)
    with pytest.raises(Reject) as rejected:
        worker_app.run_task.run({"task_id": "t-1", "kind": "model"})
    assert rejected.value.requeue is True


def test_a_duplicate_delivery_of_a_finished_task_is_skipped(monkeypatch):
    """RabbitMQ re-queues held messages when a channel closes; a finished attempt must not run again."""
    import json

    from sml_worker import runner

    kept = {"sml:task-result:t1": json.dumps({"task_id": "t1", "attempt": 1, "status": "succeeded"})}

    class FakeRedis:
        def get(self, key):  # type: ignore[no-untyped-def]
            return kept.get(key)

    monkeypatch.setattr(runner, "redis_client", lambda: FakeRedis())
    assert runner.already_finished("t1", 1)
    assert not runner.already_finished("t1", 2)  # a retry is a new attempt and runs
    assert not runner.already_finished("t2", 1)
    ran: list[str] = []
    monkeypatch.setattr(runner, "TaskContext", lambda *a, **k: ran.append("started"))
    runner.run_envelope(None, {"task_id": "t1", "attempt": 1, "kind": "model", "target": "x"})
    assert ran == []


def test_predicted_masks_are_collected_as_heatmaps(worker_env, ctx_factory):
    """P2/P3/XB-DFD publish their predicted manipulation mask instead of Grad-CAM (owner, 2026-10-01)."""
    from sml_worker.adapters.subprocess_cli import _label_for

    images = worker_env["models"] / "inference_images"
    images.mkdir()
    for name in ("abc_mask.png", "abc_face_mask.png", "abc.png", "abc_face_0.jpg"):
        (images / name).write_bytes(b"x")
    ctx = ctx_factory()
    adapter()._collect("abc", ctx)
    collected = {(a.kind, a.label) for a in ctx.artifacts}
    assert collected == {("xai", "Predicted mask"), ("xai", "Face predicted mask"), ("xai", "Original"),
                         ("face", "face 0")}
    assert _label_for("abc_mask.png", "abc") == "Predicted mask"
