"""Resident model servers keep a detector's model loaded between tasks (owner, 2026-10-01).

A launch of a resident script is handed to its server through the sitecustomize hook: the caller sees
the same output and exit code, the cached loader runs once, and without a server the script simply
runs in place (loading per task, as before).
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
import redis

from sml_worker.resident import supervisor

SERVER = Path(supervisor.__file__).with_name("server.py")

DETECTOR = textwrap.dedent('''
    import argparse, os, sys

    LOADS = []

    def load_model(path):
        LOADS.append(path)
        print(f"loading {path}", file=sys.stderr)
        return {"weights": path}

    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--input")
        p.add_argument("--fail", action="store_true")
        args = p.parse_args()
        model = load_model("w.pt")
        print(f"Fake Prob: 0.25 input={args.input} loads={len(LOADS)} cwd={os.path.basename(os.getcwd())} "
              f"flag={os.environ.get('SML_TEST_FLAG')}")
        os.system("echo child-process-output")
        return 3 if args.fail else 0

    if __name__ == "__main__":
        sys.exit(main())
''')


@pytest.fixture
def served(tmp_path: Path):  # type: ignore[no-untyped-def]
    script = tmp_path / "detector.py"
    script.write_text(DETECTOR)
    sock = tmp_path / "s.sock"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"socket": str(sock), "script": str(script), "mode": "main", "cache": ["load_model"],
                               "cwd": str(tmp_path), "warmup": [{"argv": ["--input", "warm"]}]}))
    proc = subprocess.Popen([sys.executable, str(SERVER), "--config", str(cfg)], stderr=subprocess.PIPE, text=True)
    for _ in range(100):
        if sock.exists():
            break
        time.sleep(0.05)
    assert sock.exists(), proc.stderr.read() if proc.poll() is not None else "server did not start"
    yield script, sock
    proc.terminate()
    proc.wait(timeout=10)


def launch(script: Path, sock: Path | None, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "SML_TEST_FLAG": "from-caller"}
    if sock is not None:
        env.update({"PYTHONPATH": str(supervisor.HOOK_DIR), "SML_RESIDENT": json.dumps({str(script): str(sock)})})
    return subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=60)


def test_launches_run_in_the_server_with_the_model_loaded_once(served, tmp_path):
    script, sock = served
    work = tmp_path / "work"
    work.mkdir()
    first = launch(script, sock, "--input", "a.png", cwd=work)
    second = launch(script, sock, "--input", "b.png", "--fail", cwd=work)
    assert first.returncode == 0 and second.returncode == 3
    # loads=1: the warm-up loaded the model and every run reused it
    assert "Fake Prob: 0.25 input=a.png loads=1 cwd=work flag=from-caller" in first.stdout
    assert "input=b.png loads=1" in second.stdout
    assert "child-process-output" in first.stdout  # output of the script's own child processes too
    assert "loading" not in first.stderr + second.stderr


def test_without_a_server_the_script_runs_in_place(tmp_path):
    script = tmp_path / "detector.py"
    script.write_text(DETECTOR)
    gone = tmp_path / "missing.sock"
    result = launch(script, gone, "--input", "c.png", cwd=tmp_path)
    assert result.returncode == 0 and "input=c.png loads=1" in result.stdout and "loading w.pt" in result.stderr


def test_other_python_launches_are_untouched(served, tmp_path):
    script, sock = served
    env = {**os.environ, "PYTHONPATH": str(supervisor.HOOK_DIR), "SML_RESIDENT": json.dumps({str(script): str(sock)})}
    out = subprocess.run([sys.executable, "-c", "print('plain')"], env=env, capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "plain"


def test_routing_needs_a_ready_server(monkeypatch, tmp_path):
    spec = supervisor.ServerSpec(id="m-image", model_id="m", media=["image"], script="/x/detector.py",
                                 conda_env="env", gpu="0")
    monkeypatch.setattr(supervisor, "servers", lambda: [spec])
    monkeypatch.setattr(supervisor, "resident_dir", lambda: tmp_path)
    states: dict[str, str] = {}

    class FakeRedis:
        def mget(self, keys):  # type: ignore[no-untyped-def]
            return [states.get(k) for k in keys]

    monkeypatch.setattr(supervisor, "redis_client", lambda: FakeRedis())
    assert supervisor.routing_env("m", "image") == {}
    states["sml:resident:m-image"] = json.dumps({"state": "ready"})
    assert supervisor.routing_env("m", "image") == {}  # socket missing
    Path(spec.socket).touch()
    env = supervisor.routing_env("m", "image")
    assert json.loads(env["SML_RESIDENT"]) == {"/x/detector.py": spec.socket}
    assert env["PYTHONPATH"] == str(supervisor.HOOK_DIR)
    assert supervisor.routing_env("m", "video") == {}


def test_a_task_for_a_ready_resident_model_needs_no_gpu_admission(monkeypatch):
    from sml_worker import runner

    ready: list[str] = []
    monkeypatch.setattr(runner.resident, "ready_servers", lambda model, media: ready)
    monkeypatch.setattr(runner.gpu_admission, "memory", lambda index: (23000, 0))
    envelope = {"kind": "model", "target": "skku-p2", "media_type": "image"}
    assert runner._gpu_need(envelope) > 0  # loads per task: reserves its memory first
    ready.append("skku-p2")
    assert runner._gpu_need(envelope) == 0  # its server already holds the memory


def test_a_task_waiting_for_memory_moves_to_its_resident_server_once_ready(monkeypatch, tmp_path):
    from sml_worker import runner
    from sml_worker.context import TaskContext

    ready: list[str] = []
    waits: list[int] = []

    @contextlib.contextmanager
    def admitted(task_id, need, on_wait, should_stop):  # type: ignore[no-untyped-def]
        while need:  # the GPU never has room: only the resident server can run it
            waits.append(need)
            should_stop()
            ready.append("skku-p2")  # the server finishes loading while the task waits
        yield

    monkeypatch.setattr(runner.gpu_admission, "admitted", admitted)
    monkeypatch.setattr(runner.resident, "ready_servers", lambda model, media: list(ready))
    monkeypatch.setattr(runner.gpu_admission, "memory", lambda index: (23000, 0))
    monkeypatch.setattr("sml_worker.context.redis_client", lambda: (_ for _ in ()).throw(redis.RedisError()))
    envelope = {"task_id": "t", "job_id": "j", "kind": "model", "target": "skku-p2", "media_type": "image"}
    ctx = TaskContext(envelope, tmp_path, "3")
    with runner._admission("t", envelope, ctx):
        pass
    assert len(waits) == 2 and waits[0] > 0  # waited once for memory, then ran with no reservation


SLOW = textwrap.dedent('''
    import argparse, sys, time

    def main():
        p = argparse.ArgumentParser()
        p.add_argument("--seconds", type=float)
        args = p.parse_args()
        print("started", flush=True)
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:  # a frame loop that swallows ordinary errors
            try:
                time.sleep(0.05)
            except Exception:
                pass
        print("finished", flush=True)
        return 0

    if __name__ == "__main__":
        sys.exit(main())
''')


def test_a_canceled_launch_stops_its_run_in_the_server(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text(SLOW)
    sock = tmp_path / "s.sock"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"socket": str(sock), "script": str(script), "mode": "main", "cwd": str(tmp_path)}))
    server = subprocess.Popen([sys.executable, str(SERVER), "--config", str(cfg)], stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            if sock.exists():
                break
            time.sleep(0.05)
        env = {**os.environ, "PYTHONPATH": str(supervisor.HOOK_DIR),
               "SML_RESIDENT": json.dumps({str(script): str(sock)})}
        long_run = subprocess.Popen([sys.executable, str(script), "--seconds", "60"], cwd=tmp_path, env=env,
                                    stdout=subprocess.PIPE, text=True)
        assert long_run.stdout.readline().strip() == "started"
        long_run.kill()  # the worker kills the launch when its job is canceled
        long_run.wait()
        started = time.monotonic()
        next_run = launch(script, sock, "--seconds", "0", cwd=tmp_path)
        assert next_run.returncode == 0 and "finished" in next_run.stdout
        assert time.monotonic() - started < 15  # did not wait for the abandoned 60 s run
    finally:
        server.terminate()
        _, err = server.communicate(timeout=10)
    assert "the caller went away; stopping the run" in err and "exited 130" in err


def test_a_task_waits_for_a_loading_server_instead_of_loading_a_second_copy(monkeypatch, tmp_path):
    from sml_worker import runner
    from sml_worker.context import TaskContext

    states = iter([["loading"], ["loading"], ["ready"]])
    seen: list[str] = []

    def loading(model, media):  # type: ignore[no-untyped-def]
        current = next(states, ["ready"])
        seen.append(current[0])
        return ["skku-p2"] if current == ["loading"] else []

    monkeypatch.setattr(runner.resident, "loading_servers", loading)
    monkeypatch.setattr(runner.resident, "ready_servers", lambda model, media: [])
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr("sml_worker.context.redis_client", lambda: (_ for _ in ()).throw(redis.RedisError()))
    envelope = {"task_id": "t", "job_id": "j", "kind": "model", "target": "skku-p2", "media_type": "video"}
    runner._await_resident(envelope, TaskContext(envelope, tmp_path, "0"))
    assert seen == ["loading", "loading", "ready"]  # waited while loading, went on once it was not

    monkeypatch.setattr(runner, "RESIDENT_LOAD_WAIT_SECONDS", -1)  # a server that never finishes loading
    monkeypatch.setattr(runner.resident, "loading_servers", lambda model, media: ["skku-p2"])
    runner._await_resident(envelope, TaskContext(envelope, tmp_path, "0"))  # gives up and returns
