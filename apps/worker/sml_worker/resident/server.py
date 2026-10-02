"""Resident model server: keeps one detector script's model loaded on its GPU (owner, 2026-10-01).

Run by the supervisor (`python -m sml_worker --resident`) with the model's own conda Python, so it
uses only the standard library. It serves the registered script exactly as if it were launched:

* `mode: main` imports the script once and calls its `main()` per request;
* `mode: run` re-runs the script per request (`runpy`), for scripts whose `main` takes arguments or
  that work at module level.

Either way the loaders named in `cache` (functions or classes, in the script or in modules it
imports, as `name` or `module:name`) return the object from their first call for the same
arguments, and `torch_load_cache` keeps checkpoints read by `torch.load` in memory, so weights are
read and moved to the GPU once. Each request carries the caller's argv, working directory and
environment; its stdout/stderr (including native and child-process output) stream back over the
Unix socket, followed by the exit code. Requests run one at a time.

Clients are launches of the script itself, redirected here by `hook/sitecustomize.py`.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import gc
import importlib
import importlib.util
import json
import os
import runpy
import select
import signal
import socket
import socketserver
import sys
import threading
import time
import traceback

# Never forwarded into a run: the server's GPU and import path are its own, and routing a nested
# launch back to this (busy) server would deadlock.
KEEP_OWN_ENV = ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "PYTHONPATH", "SML_RESIDENT")


def log(msg: str) -> None:
    sys.__stderr__.write(f"[resident {time.strftime('%H:%M:%S')}] {msg}\n")
    sys.__stderr__.flush()


# --- caching ---------------------------------------------------------------------------------------

def _freeze(value, depth: int = 0):
    """A hashable, content-based key for loader arguments (objects fall back to their identity)."""
    if depth > 6:
        return ("id", id(value))
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    if isinstance(value, dict):
        return ("dict", tuple(sorted((str(k), _freeze(v, depth + 1)) for k, v in value.items())))
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=repr) if isinstance(value, (set, frozenset)) else value
        return (type(value).__name__, tuple(_freeze(v, depth + 1) for v in items))
    if isinstance(value, os.PathLike):
        return ("path", os.fspath(value))
    if isinstance(value, argparse.Namespace):
        return _freeze(vars(value), depth + 1)
    if type(value).__name__ in ("device", "dtype"):
        return ("repr", repr(value))
    return ("id", id(value))


def cached(fn, label: str):
    store: dict = {}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (_freeze(args), _freeze(kwargs))
        if key not in store:
            started = time.monotonic()
            store[key] = fn(*args, **kwargs)
            log(f"loaded {label} in {time.monotonic() - started:.1f}s")
        return store[key]

    wrapper.__sml_cached__ = True  # type: ignore[attr-defined]
    return wrapper


def install_torch_load_cache() -> None:
    import copy

    import torch

    original = torch.load
    store: dict = {}

    @functools.wraps(original)
    def load(f, *args, **kwargs):
        if not isinstance(f, (str, os.PathLike)):
            return original(f, *args, **kwargs)
        path = os.path.realpath(os.fspath(f))
        key = (path, os.path.getmtime(path), repr(kwargs.get("map_location", args[0] if args else None)))
        if key not in store:
            store[key] = original(f, *args, **kwargs)
            log(f"cached torch.load({path})")
        obj = store[key]
        return copy.copy(obj) if isinstance(obj, dict) else obj  # callers may pop top-level keys

    torch.load = load


def patch(namespace, name: str, label: str) -> None:
    target = getattr(namespace, name)
    if not getattr(target, "__sml_cached__", False):
        setattr(namespace, name, cached(target, label))


# --- one run of the script -----------------------------------------------------------------------

class ClientGone(BaseException):
    """The launch that asked for this run went away (its task was canceled or timed out).

    A BaseException, so scripts' `except Exception` blocks do not swallow it."""


INTERRUPTIBLE = threading.Event()  # set only while a request's script is running


def _interrupt(_signum, _frame) -> None:
    if INTERRUPTIBLE.is_set():
        raise ClientGone()


def watch_client(conn: socket.socket, done: threading.Event) -> None:
    """Stop the run when its caller disconnects, instead of finishing work nobody waits for (a long
    video would otherwise keep every later task of this model waiting). The run is interrupted in the
    main thread at its next Python instruction; a script that swallows it is asked again every 5 s."""
    while not done.is_set():
        readable, _, _ = select.select([conn], [], [], 1.0)
        if not readable:
            continue
        try:
            data = conn.recv(1, socket.MSG_PEEK)
        except OSError:
            data = b""
        if data:
            time.sleep(1.0)  # the caller sends nothing after its request; ignore stray bytes
            continue
        log("the caller went away; stopping the run")
        while not done.is_set():
            if INTERRUPTIBLE.is_set():
                signal.pthread_kill(threading.main_thread().ident, signal.SIGUSR1)
            done.wait(5.0)
        return

class Script:
    def __init__(self, cfg: dict) -> None:
        self.path = os.path.realpath(cfg["script"])
        self.mode = cfg.get("mode", "run")
        self.cache = list(cfg.get("cache", []))
        self.module = None
        sys.path.insert(0, os.path.dirname(self.path))
        if self.mode == "main":
            spec = importlib.util.spec_from_file_location("sml_resident_script", self.path)
            self.module = importlib.util.module_from_spec(spec)
            sys.modules["sml_resident_script"] = self.module
            spec.loader.exec_module(self.module)
        for entry in self.cache:
            if ":" in entry:
                mod_name, attr = entry.split(":", 1)
                patch(importlib.import_module(mod_name), attr, entry)
            elif self.module is not None:
                patch(self.module, entry, entry)
            else:
                raise ValueError(f"cache entry {entry!r} needs module:name in run mode")

    def run(self, argv: list) -> int:
        sys.argv = [self.path, *argv[1:]]
        try:
            if self.mode == "main":
                result = self.module.main()
                return result if isinstance(result, int) else 0  # `sys.exit(main())` scripts
            runpy.run_path(self.path, run_name="__main__")
            return 0
        except ClientGone:
            return 130
        except SystemExit as exc:
            if exc.code is None:
                return 0
            if isinstance(exc.code, int):
                return exc.code
            print(exc.code, file=sys.stderr)
            return 1
        except BaseException:  # noqa: BLE001 - report like an uncaught exception would
            traceback.print_exc()
            return 1


@contextlib.contextmanager
def request_context(cwd: str, env: dict):
    saved_cwd, saved_path, saved_argv = os.getcwd(), list(sys.path), list(sys.argv)
    saved_env = {}
    for key, value in env.items():
        if key in KEEP_OWN_ENV:
            continue
        saved_env[key] = os.environ.get(key)
        os.environ[key] = value
    os.chdir(cwd)
    try:
        yield
    finally:
        os.chdir(saved_cwd)
        sys.path[:] = saved_path
        sys.argv = saved_argv
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextlib.contextmanager
def captured_output(send):
    """Points fds 1 and 2 at pipes whose contents are sent to the client (Python, native and child
    output alike) and restores them afterwards."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    readers = []
    for fd, stream in ((1, "out"), (2, "err")):
        read_end, write_end = os.pipe()
        os.dup2(write_end, fd)
        os.close(write_end)

        def pump(read_end=read_end, stream=stream):
            with os.fdopen(read_end, "rb", buffering=0) as pipe:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk:
                        return
                    send({stream: chunk.decode("utf-8", "replace")})

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        readers.append(thread)
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            sys.stdout.flush()
            sys.stderr.flush()
        os.dup2(saved[0], 1)
        os.dup2(saved[1], 2)
        os.close(saved[0])
        os.close(saved[1])
        for thread in readers:
            thread.join(timeout=30)


def free_gpu_cache() -> None:
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None:
        with contextlib.suppress(Exception):
            if torch.cuda.is_initialized():
                torch.cuda.empty_cache()


# --- serving ---------------------------------------------------------------------------------------

class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
        request = json.loads(raw)
        lock = threading.Lock()
        alive = [True]

        def send(message: dict) -> None:
            if not alive[0]:
                return
            data = (json.dumps(message) + "\n").encode()
            with lock:
                try:
                    self.wfile.write(data)
                    self.wfile.flush()
                except OSError:
                    alive[0] = False  # the caller went away (canceled or timed out); finish anyway

        if request.get("ping"):
            send({"pong": {"script": SERVER.script.path, "runs": SERVER.runs}})
            return
        started = time.monotonic()
        SERVER.busy_since = started
        done = threading.Event()
        threading.Thread(target=watch_client, args=(self.connection, done), daemon=True).start()
        try:
            with request_context(request["cwd"], request.get("env") or {}), captured_output(send):
                INTERRUPTIBLE.set()
                try:
                    code = SERVER.script.run(request["argv"])
                finally:
                    INTERRUPTIBLE.clear()
        except ClientGone:  # raised just outside the script (e.g. while restoring the context)
            code = 130
        finally:
            done.set()
        SERVER.busy_since = None
        free_gpu_cache()
        SERVER.runs += 1
        log(f"run {SERVER.runs} exited {code} in {time.monotonic() - started:.1f}s")
        send({"exit": code})


class Server(socketserver.UnixStreamServer):
    request_queue_size = 64

    def __init__(self, path: str, script: Script, max_run_seconds: float) -> None:
        self.script = script
        self.runs = 0
        self.busy_since: float | None = None
        self.max_run_seconds = max_run_seconds
        super().__init__(path, Handler)
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _watchdog(self) -> None:
        """A run cannot be interrupted from outside, and every later run of this model would queue behind
        it, so a run past the model's time limit ends the server; the supervisor starts a fresh one."""
        while True:
            time.sleep(5)
            busy = self.busy_since
            if busy is not None and self.max_run_seconds and time.monotonic() - busy > self.max_run_seconds:
                log(f"a run exceeded {self.max_run_seconds:.0f}s; exiting so the supervisor restarts the server")
                os._exit(70)


SERVER: Server



def remove_own_socket(path: str, inode: int) -> None:
    """Remove the socket only if it is still ours: a newer server may have bound the same path."""
    with contextlib.suppress(OSError):
        if os.stat(path).st_ino == inode:
            os.unlink(path)


def main() -> None:
    global SERVER
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="JSON: socket, script, mode, cache, cwd, warmup, ...")
    with open(parser.parse_args().config, encoding="utf-8") as fh:
        cfg = json.load(fh)

    os.chdir(cfg.get("cwd") or os.path.dirname(cfg["script"]))
    if cfg.get("torch_load_cache"):
        install_torch_load_cache()
    started = time.monotonic()
    script = Script(cfg)
    for warmup in cfg.get("warmup", []):  # loads the weights before the first real request
        log(f"warm-up: {' '.join(warmup['argv'])}")
        with request_context(warmup.get("cwd") or os.getcwd(), warmup.get("env") or {}):
            code = script.run([script.path, *warmup["argv"]])
        free_gpu_cache()
        log(f"warm-up exited {code}")
    log(f"ready in {time.monotonic() - started:.0f}s")

    path = cfg["socket"]
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)  # left over from a previous run
    os.makedirs(os.path.dirname(path), exist_ok=True)
    SERVER = Server(path, script, float(cfg.get("max_run_seconds") or 0))  # binding last: socket = ready
    os.chmod(path, 0o600)
    bound = os.stat(path).st_ino
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # remove the socket on the way out
    signal.signal(signal.SIGUSR1, _interrupt)  # watch_client: the caller of the current run went away
    try:
        SERVER.serve_forever()
    finally:
        remove_own_socket(path, bound)


if __name__ == "__main__":
    main()
