"""Image studio jobs on the worker (owner, 2026-10-01): the prompt check, consent for faces and the
NSFW filter come before any image is made; outputs become the user's media."""

from __future__ import annotations

import importlib.util
import inspect
import json
import socketserver
import threading
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from sml_worker.adapters.base import AdapterError
from sml_worker.studio import client, safety, task

SERVER_FILE = Path(task.__file__).with_name("server.py")


class FakeStudio:
    """Speaks the studio server's protocol; `checks` and `done` script its answers."""

    def __init__(self, sock: Path, out: Path) -> None:
        self.requests: list[dict[str, Any]] = []
        self.checks = [{"faces": 0, "nsfw": 0.01}]
        self.done: dict[str, Any] | None = None
        self.error: dict[str, Any] | None = None
        studio = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                req = json.loads(self.rfile.readline())
                studio.requests.append(req)

                def send(msg: dict[str, Any]) -> None:
                    self.wfile.write((json.dumps(msg) + "\n").encode())

                if req["op"] == "check":
                    send({"checks": studio.checks[: len(req["images"])]})
                    return
                send({"event": "status", "message": "Loading the model"})
                for step in range(5):
                    send({"event": "progress", "image": 0, "images": 1, "step": step, "steps": 4})
                if studio.error:
                    send({"error": studio.error})
                    return
                outputs = []
                for i in range(req["count"]):
                    path = out / f"output_{i + 1}.png"
                    Image.new("RGBA", (64, 32), (255, 0, 0, 128)).save(path)
                    outputs.append({"path": str(path), "seed": req["seed"] + i, "width": 64, "height": 32,
                                    "transparent": True})
                send({"done": studio.done or {"outputs": outputs, "blocked": 0, "model": req["model"],
                                              "seed": req["seed"]}})

        self.server = socketserver.ThreadingUnixStreamServer(str(sock), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker_env):  # type: ignore[no-untyped-def]
    out = tmp_path / "server-out"
    out.mkdir()
    fake = FakeStudio(tmp_path / "studio.sock", out)
    monkeypatch.setattr(client, "socket_path", lambda: str(tmp_path / "studio.sock"))
    monkeypatch.setattr(task, "check_prompt", lambda *a, **k: safety.Verdict(True))
    monkeypatch.setattr(task, "download", lambda key, dest: Image.new("RGB", (8, 8)).save(dest) or dest)
    stored: list[str] = []
    monkeypatch.setattr(task, "upload", lambda path, key: (stored.append(key), (key, "image/png", 10))[1])
    fake.stored = stored  # type: ignore[attr-defined]
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def envelope(**studio: Any) -> dict[str, Any]:
    return {"task_id": "t1", "job_id": "job-1", "user_id": "user-1", "kind": "studio",
            "studio": {"mode": "generate", "model": "qwen-image-2512", "prompt": "a fox", "count": 2, "seed": 10,
                       "references": [], **studio}}


def test_outputs_are_uploaded_as_the_users_media_with_thumbnails(studio, ctx_factory):
    ctx = ctx_factory()
    result = task.run_studio(envelope(), ctx).as_dict()
    assert [o["seed"] for o in result["outputs"]] == [10, 11] and result["blocked"] == 0
    first = result["outputs"][0]
    assert first["storage_key"] == f"media/u/user-1/{first['id']}.png"
    assert first["thumbnail_key"] == f"thumbs/u/user-1/{first['id']}.jpg" and first["transparent"]
    assert len(studio.stored) == 4
    sent = studio.requests[-1]
    assert sent["op"] == "generate" and sent["model"] == "qwen-image-2512" and sent["images"] == []


def test_faces_in_references_need_consent(studio, ctx_factory):
    studio.checks = [{"faces": 1, "nsfw": 0.02}]
    refs = [{"storage_key": "media/u/user-1/a.png", "extension": "png"}]
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(mode="edit", references=refs), ctx_factory())
    assert exc.value.code == "CONSENT_REQUIRED"
    assert [r["op"] for r in studio.requests] == ["check"]  # nothing was generated
    result = task.run_studio(envelope(mode="edit", references=refs, consent=True), ctx_factory("t2")).as_dict()
    assert result["faces"] == 1 and len(result["outputs"]) == 2


def test_nsfw_references_and_refused_prompts_are_never_generated(studio, ctx_factory, monkeypatch):
    studio.checks = [{"faces": 0, "nsfw": 0.9}]
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(mode="edit", references=[{"storage_key": "k", "extension": "png"}]), ctx_factory())
    assert exc.value.code == "INPUT_BLOCKED"
    monkeypatch.setattr(task, "check_prompt", lambda *a, **k: safety.Verdict(False, "violence", "gore"))
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(), ctx_factory("t2"))
    assert exc.value.code == "PROMPT_BLOCKED"

    def unavailable(*_a: Any, **_k: Any) -> Any:
        raise safety.SafetyUnavailable("ollama down")

    monkeypatch.setattr(task, "check_prompt", unavailable)
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(), ctx_factory("t3"))
    assert exc.value.code == "SAFETY_UNAVAILABLE"  # fails closed
    assert all(r["op"] == "check" for r in studio.requests)


def test_withheld_outputs_and_server_errors_are_classified(studio, ctx_factory):
    studio.done = {"outputs": [], "blocked": 2}
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(), ctx_factory())
    assert exc.value.code == "OUTPUT_BLOCKED"
    studio.done, studio.error = None, {"code": "GPU_OOM", "message": "CUDA out of memory"}
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(), ctx_factory("t2"))
    assert exc.value.code == "GPU_OOM"


def test_without_a_server_the_job_fails_cleanly(studio, ctx_factory, monkeypatch, tmp_path):
    monkeypatch.setattr(client, "socket_path", lambda: str(tmp_path / "missing.sock"))
    with pytest.raises(AdapterError) as exc:
        task.run_studio(envelope(), ctx_factory())
    assert exc.value.code == "STUDIO_UNAVAILABLE"


@pytest.mark.parametrize("prompt, blocked", [
    ("a nude child", True), ("아동의 누드 사진", True), ("sextant on a kid's desk", False),
    ("a teen playing football", False), ("a naked mole-rat", False),
])
def test_sexual_content_with_minors_is_refused_before_the_llm(prompt, blocked, monkeypatch):
    def llm(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("the LLM is not asked")

    monkeypatch.setattr(safety.httpx, "post", llm)
    if blocked:
        assert safety.check_prompt(prompt, "", "m").category == "minors"
    else:
        assert not any(p.search(prompt) for p in safety._BLOCK)


def _server_module() -> Any:
    spec = importlib.util.spec_from_file_location("studio_server", SERVER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # stdlib only at import time; torch is imported where used
    return module


def test_the_controls_map_onto_each_pipelines_arguments():
    server = _server_module()

    class EditPipe:
        def __call__(self, image=None, prompt=None, negative_prompt=None, true_cfg_scale=4.0, height=None,
                     width=None, num_inference_steps=50, guidance_scale=None, generator=None,
                     callback_on_step_end=None):
            ...

    entry = {"id": "edit", "pipeline": "EditPipe",
             "call": {"steps": "num_inference_steps", "guidance": "true_cfg_scale",
                      "negative_prompt": "negative_prompt", "images": "image", "fixed": {"guidance_scale": 1.0}},
             "default_negative_prompt": " ", "capabilities": {"steps": {"default": 40}, "guidance": {"default": 4.0}}}
    kwargs = server.Studio._kwargs(None, entry, EditPipe(), {"prompt": " add a hat ", "width": 512, "height": 512},
                                   ["img1", "img2"], "edit")
    assert kwargs == {"prompt": "add a hat", "guidance_scale": 1.0, "image": ["img1", "img2"],
                      "num_inference_steps": 40, "true_cfg_scale": 4.0, "negative_prompt": " "}

    class T2IPipe:
        def __call__(self, prompt=None, image=None, height=None, width=None, num_inference_steps=40,
                     generator=None):
            ...

    entry = {"id": "t2i", "pipeline": "T2IPipe", "call": {"steps": "num_inference_steps", "size": "generate"},
             "transparent_prompt": "RGBA. {prompt} Transparent.", "capabilities": {"transparent": True}}
    req = {"prompt": "a sticker", "transparent": True, "width": 2048, "height": 1536, "steps": 20}
    kwargs = server.Studio._kwargs(None, entry, T2IPipe(), req, [], "generate")
    assert kwargs == {"prompt": "RGBA. a sticker Transparent.", "num_inference_steps": 20, "width": 2048,
                      "height": 1536}
    entry["call"]["guidance"] = "true_cfg_scale"
    with pytest.raises(server.StudioError):  # the config names an argument the pipeline lacks
        server.Studio._kwargs(None, entry, T2IPipe(), {"prompt": "x", "guidance": 3.0}, [], "generate")
    assert "callback_on_step_end" not in inspect.signature(T2IPipe.__call__).parameters


def test_the_supervisor_runs_the_studio_server_when_its_env_exists(worker_env, monkeypatch):
    from sml_worker import studio as studio_pkg
    from sml_worker.resident import supervisor

    monkeypatch.setattr(studio_pkg, "studio_config", lambda: {"server": {"conda_env": "fake", "gpu": "1"}})
    spec = supervisor.studio_servers()[0]
    assert (spec.id, spec.kind, spec.gpu, spec.conda_env) == ("studio", "studio", "1", "fake")
    monkeypatch.setattr(studio_pkg, "studio_config", lambda: {"server": {"conda_env": "missing"}})
    assert supervisor.studio_servers() == []
    cfg = studio_pkg.server_config("/tmp/s.sock", ["m1"])
    assert cfg["socket"] == "/tmp/s.sock" and cfg["keep"] == ["m1"]


def test_the_admins_models_stay_loaded_in_order_of_preference():
    server = _server_module()
    studio = object.__new__(server.Studio)
    studio.models = {m: {"id": m, "work_gb": 8} for m in ("gen", "edit", "small")}
    studio.inventory = {"gen": (True, 54.0), "edit": (True, 54.0), "small": (True, 15.0)}
    studio.budget_gb = 66
    studio.keep = ["gen", "edit"]
    assert studio.target() == ["gen"]  # both do not fit: generation first, edits swap in on demand
    studio.keep = ["edit", "small"]
    assert studio.target() == ["edit"]
    studio.budget_gb = 90
    assert studio.target() == ["edit", "small"]
    studio.inventory["edit"] = (False, 0.0)  # not downloaded
    assert studio.target() == ["small"]
