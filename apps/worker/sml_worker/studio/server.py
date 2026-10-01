"""Image studio server: generates and edits images with the diffusers models of config/studio.yaml.

Run by the resident supervisor (`python -m sml_worker --resident`) with the `imagegen` env's Python on
the studio GPU, so it imports nothing from sml_worker. The models the admin picked for users stay
loaded (owner, 2026-10-01); a request for another model swaps it in, evicting what does not fit in
the memory budget, and once the studio has been idle the admin's models are loaded again.

One JSON request per connection over a Unix socket; JSON lines come back:

    {"op": "status"}                     -> {"status": {...}}
    {"op": "keep", "models": [ids]}      -> {"ok": true}           (the admin's models, in order)
    {"op": "check", "images": [paths]}   -> {"checks": [{"faces": n, "nsfw": p}, ...]}
    {"op": "generate", ...}              -> {"event": "status" | "progress", ...}* then
                                            {"done": {"outputs": [...], "blocked": n}} or {"error": {...}}

Requests that use the GPU run one at a time; a client that disconnects cancels its request at the
next denoising step. A request running past `max_request_seconds` ends the server (the supervisor
starts a fresh one), as a stuck CUDA call cannot be interrupted.
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import glob
import inspect
import json
import os
import random
import signal
import socketserver
import sys
import threading
import time
import traceback

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
# Models of very different sizes come and go: expandable segments keep freed memory reusable.
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

GB = 1024 ** 3


def log(msg: str) -> None:
    sys.stderr.write(f"[studio {time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()


class StudioError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Canceled(Exception):
    """The client went away (job canceled or timed out)."""


# --- model files ------------------------------------------------------------------------------------

def snapshot_dir(repo: str) -> str | None:
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(repo, local_files_only=True)
    except Exception:  # noqa: BLE001 - not downloaded (or not completely)
        return None


def _component_dirs(path: str) -> list[str]:
    with open(os.path.join(path, "model_index.json"), encoding="utf-8") as fh:
        index = json.load(fh)
    return [os.path.join(path, name) for name, value in index.items()
            if isinstance(value, list) and os.path.isdir(os.path.join(path, name))]


def installed(repo: str) -> tuple[bool, float]:
    """(complete, weights in GB): every component's weights are on disk, shards included."""
    path = snapshot_dir(repo)
    if path is None or not os.path.exists(os.path.join(path, "model_index.json")):
        return False, 0.0
    size = 0
    for comp in _component_dirs(path):
        for index_file in glob.glob(os.path.join(comp, "*.safetensors.index.json")):
            with open(index_file, encoding="utf-8") as fh:
                shards = set(json.load(fh).get("weight_map", {}).values())
            if not all(os.path.exists(os.path.join(comp, s)) for s in shards):
                return False, 0.0
        size += sum(os.path.getsize(f) for f in glob.glob(os.path.join(comp, "*.safetensors")))
    return size > 0, size / GB


# --- safety checks -------------------------------------------------------------------------------

def flatten(image):
    """RGB as a viewer sees it: transparent areas on white (their hidden colour is often black)."""
    from PIL import Image

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        canvas.alpha_composite(rgba)
        return canvas.convert("RGB")
    return image.convert("RGB")


class Checks:
    """NSFW classifier (timm ViT, the platform's NSFW check) and face detector (SCRFD), loaded lazily."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.nsfw_model = None
        self.nsfw_transform = None
        self.nsfw_index = 0
        self.faces = None

    def nsfw(self, image) -> float:
        import torch

        if self.nsfw_model is None:
            import safetensors.torch
            import timm

            model_dir = self.cfg["nsfw_model_dir"]
            with open(os.path.join(model_dir, "config.json"), encoding="utf-8") as fh:
                meta = json.load(fh)
            model = timm.create_model(meta["architecture"], pretrained=False, num_classes=meta["num_classes"],
                                      global_pool=meta["global_pool"])
            model.load_state_dict(safetensors.torch.load_file(os.path.join(model_dir, "model.safetensors")))
            pc = dict(model.pretrained_cfg or {})
            pc.update(meta.get("pretrained_cfg") or {})
            model.pretrained_cfg = pc
            self.nsfw_model = model.eval().to("cuda")
            data_cfg = timm.data.resolve_model_data_config(model)
            self.nsfw_transform = timm.data.create_transform(**data_cfg, is_training=False)
            self.nsfw_index = [n.lower() for n in meta["label_names"]].index("nsfw")
            log("loaded the NSFW classifier")
        rgb = flatten(image)
        with torch.inference_mode():
            logits = self.nsfw_model(self.nsfw_transform(rgb).unsqueeze(0).to("cuda"))
            return float(logits.softmax(dim=-1)[0, self.nsfw_index])

    def face_count(self, image) -> int:
        import numpy as np

        if self.faces is None:
            from insightface.model_zoo import get_model

            self.faces = get_model(os.path.expanduser(self.cfg["face_detector"]),
                                   providers=["CPUExecutionProvider"])
            self.faces.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=float(self.cfg.get("face_min_score", 0.6)))
            log("loaded the face detector")
        bgr = np.ascontiguousarray(np.asarray(flatten(image))[:, :, ::-1])
        boxes, _ = self.faces.detect(bgr, max_num=0)
        return len(boxes)


# --- models ------------------------------------------------------------------------------------------

class Loaded:
    def __init__(self, entry: dict, pipe, weights_gb: float):
        self.entry = entry
        self.pipe = pipe
        self.weights_gb = weights_gb
        self.used_at = time.monotonic()


class Studio:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.models = {m["id"]: m for m in cfg["models"]}
        self.keep: list[str] = list(cfg.get("keep") or [])
        self.loaded: dict[str, Loaded] = {}
        self.loading: str | None = None
        self.gpu = threading.Lock()
        self.waiting = 0
        self.busy_since: float | None = None
        self.last_request = time.monotonic()
        self.checks = Checks(cfg["safety"])
        self.budget_gb = float(cfg.get("memory_budget_gb") or 60)
        self.inventory = {mid: installed(m["repo"]) for mid, m in self.models.items()}

    # -- memory ------------------------------------------------------------------------------------

    def _need_gb(self, entry: dict) -> float:
        return self.inventory[entry["id"]][1] + float(entry.get("work_gb", 8))

    def _held_gb(self) -> float:
        return sum(lm.weights_gb + float(lm.entry.get("work_gb", 8)) for lm in self.loaded.values())

    @staticmethod
    def _device_free_gb() -> float:
        import torch

        free, _ = torch.cuda.mem_get_info()
        return free / GB

    def _fits(self, entry: dict) -> bool:
        need = self._need_gb(entry)
        return self._held_gb() + need <= self.budget_gb and self._device_free_gb() >= self.inventory[entry["id"]][1] + 1

    def _unload(self, model_id: str) -> None:
        import torch

        lm = self.loaded.pop(model_id, None)
        if lm is None:
            return
        del lm.pipe
        gc.collect()
        torch.cuda.empty_cache()
        log(f"unloaded {model_id}")

    def ensure(self, model_id: str, send=lambda _m: None):
        """The pipeline of `model_id`, loading it (and evicting others) if needed. Holds self.gpu."""
        if model_id in self.loaded:
            self.loaded[model_id].used_at = time.monotonic()
            return self.loaded[model_id].pipe
        entry = self.models.get(model_id)
        if entry is None:
            raise StudioError("MODEL_UNAVAILABLE", f"Unknown studio model {model_id}.")
        ok, weights_gb = self.inventory[model_id] = installed(entry["repo"])
        if not ok:
            raise StudioError("MODEL_UNAVAILABLE", f"{model_id} is not downloaded ({entry['repo']}).")
        # Evict models not asked to stay first, then the admin's in reverse order of preference.
        order = sorted(self.loaded, key=lambda m: (m in self.keep, -self.keep.index(m) if m in self.keep else 0,
                                                   self.loaded[m].used_at))
        while self.loaded and not self._fits(entry):
            self._unload(order.pop(0))
        if not self._fits(entry):
            raise StudioError("GPU_OOM", f"{model_id} needs {self._need_gb(entry):.0f} GB; "
                                         f"{self._device_free_gb():.0f} GB free on the studio GPU.")
        send({"event": "status", "message": "Loading the model"})
        self.loaded[model_id] = Loaded(entry, self._load(entry), weights_gb)
        return self.loaded[model_id].pipe

    def _load(self, entry: dict):
        import diffusers
        import torch

        self.loading = entry["id"]
        started = time.monotonic()
        try:
            cls = getattr(diffusers, entry["pipeline"])
            pipe = cls.from_pretrained(entry["repo"], torch_dtype=torch.bfloat16, local_files_only=True)
            if entry.get("offload") == "model":
                pipe.enable_model_cpu_offload()
            else:
                pipe.to("cuda")
            pipe.set_progress_bar_config(disable=True)
        finally:
            self.loading = None
        log(f"loaded {entry['id']} in {time.monotonic() - started:.0f}s")
        return pipe

    def evict_others(self, model_id: str) -> bool:
        others = [m for m in self.loaded if m != model_id]
        for other in others:
            self._unload(other)
        free_cuda()
        return bool(others)

    def target(self) -> list[str]:
        """The admin's models that stay loaded: in order of preference, as many as the budget holds."""
        out, held = [], 0.0
        for model_id in self.keep:
            if model_id not in self.models or not self.inventory.get(model_id, (False, 0.0))[0]:
                continue
            need = self._need_gb(self.models[model_id])
            if held + need <= self.budget_gb:
                out.append(model_id)
                held += need
        return out

    def restore(self) -> bool:
        """Back to the admin's models (holds self.gpu): unload the others, load the missing ones."""
        target = self.target()
        for model_id in [m for m in self.loaded if m not in target]:
            self._unload(model_id)
        ok = True
        for model_id in target:
            if model_id in self.loaded:
                continue
            try:
                self.ensure(model_id)
            except Exception:  # noqa: BLE001 - keep serving; a request reports the error
                log(f"could not load {model_id}:\n{traceback.format_exc()}")
                ok = False
        return ok

    def status(self) -> dict:
        try:
            free = round(self._device_free_gb(), 1)
        except Exception:  # noqa: BLE001
            free = None
        return {
            "loaded": list(self.loaded), "loading": self.loading, "keep": self.keep,
            "busy": self.busy_since is not None, "waiting": self.waiting, "device_free_gb": free,
            "budget_gb": self.budget_gb,
            "models": {mid: {"installed": ok, "weights_gb": round(gb, 1)} for mid, (ok, gb) in self.inventory.items()},
        }

    # -- requests -----------------------------------------------------------------------------------

    @contextlib.contextmanager
    def turn(self, send):
        self.waiting += 1
        try:
            if not self.gpu.acquire(blocking=False):
                send({"event": "status", "message": "Waiting for the studio"})
                self.gpu.acquire()
        finally:
            self.waiting -= 1
        self.busy_since = time.monotonic()
        try:
            yield
        finally:
            self.busy_since = None
            self.last_request = time.monotonic()
            self.gpu.release()

    def check(self, paths: list[str], send) -> list[dict]:
        from PIL import Image

        out = []
        with self.turn(send):
            for path in paths:
                with Image.open(path) as img:
                    img.load()
                    out.append({"faces": self.checks.face_count(img), "nsfw": round(self.checks.nsfw(img), 4)})
        return out

    def generate(self, req: dict, send, alive) -> dict:
        import torch
        from PIL import Image

        entry = self.models.get(req.get("model", ""))
        if entry is None:
            raise StudioError("MODEL_UNAVAILABLE", f"Unknown studio model {req.get('model')}.")
        mode = req.get("mode", "generate")
        if mode not in entry.get("modes", []):
            raise StudioError("CONFIG_ERROR", f"{entry['id']} does not support {mode}.")
        call = entry.get("call") or {}
        refs = []
        for path in req.get("images") or []:
            img = Image.open(path)
            img.load()
            transparent_ok = (entry.get("capabilities") or {}).get("transparent")
            refs.append(img if transparent_ok and img.mode == "RGBA" else img.convert("RGB"))
        count = max(1, int(req.get("count") or 1))
        base_seed = req.get("seed")
        base_seed = int(base_seed) if base_seed is not None else random.randint(0, 2**31 - 1)  # noqa: S311 - a seed, not a secret
        threshold = float(self.cfg["safety"].get("nsfw_threshold", 0.5))
        out_dir = req["output_dir"]
        os.makedirs(out_dir, exist_ok=True)

        with self.turn(send):
            pipe = self.ensure(entry["id"], send)
            torch.cuda.reset_peak_memory_stats()
            kwargs = self._kwargs(entry, pipe, req, refs, mode)
            steps = int(kwargs.get(call.get("steps", "num_inference_steps"), 0) or 0)
            accepts_callback = "callback_on_step_end" in inspect.signature(pipe.__call__).parameters
            device = "cpu" if entry.get("offload") == "model" else "cuda"
            outputs, blocked = [], 0
            for index in range(count):
                if not alive():
                    raise Canceled()
                seed = base_seed + index
                send({"event": "progress", "image": index, "images": count, "step": 0, "steps": steps})

                def on_step(_pipe, step, _timestep, callback_kwargs, index=index):
                    if not alive():
                        raise Canceled()
                    send({"event": "progress", "image": index, "images": count, "step": step + 1, "steps": steps})
                    return callback_kwargs

                extra = {"callback_on_step_end": on_step} if accepts_callback else {}
                for attempt in (1, 2):
                    try:
                        with torch.inference_mode():
                            image = pipe(**kwargs, generator=torch.Generator(device).manual_seed(seed),
                                         **extra).images[0]
                        break
                    except torch.OutOfMemoryError:
                        # The working memory estimate was short: make room by evicting the other models.
                        if attempt == 2 or not self.evict_others(entry["id"]):
                            raise
                        send({"event": "status", "message": "Freeing GPU memory"})
                score = self.checks.nsfw(image)
                if score >= threshold:
                    blocked += 1
                    log(f"output {index + 1}/{count} withheld by the safety filter ({score:.2f})")
                    continue
                path = os.path.join(out_dir, f"output_{index + 1}.png")
                image.save(path)
                outputs.append({"path": path, "seed": seed, "width": image.width, "height": image.height,
                                "transparent": image.mode == "RGBA", "nsfw": round(score, 4)})
            send({"event": "status", "message": "Finishing"})
            peak_gb = torch.cuda.max_memory_reserved() / GB
        log(f"{entry['id']} {mode}: {len(outputs)}/{count} delivered, peak {peak_gb:.1f} GB reserved")
        return {"outputs": outputs, "blocked": blocked, "model": entry["id"], "seed": base_seed,
                "peak_gb": round(peak_gb, 1)}

    def _kwargs(self, entry: dict, pipe, req: dict, refs: list, mode: str) -> dict:
        call = entry.get("call") or {}
        caps = entry.get("capabilities") or {}
        params = inspect.signature(pipe.__call__).parameters
        prompt = str(req.get("prompt") or "").strip()
        if req.get("transparent") and caps.get("transparent") and entry.get("transparent_prompt"):
            prompt = entry["transparent_prompt"].format(prompt=prompt)
        kwargs: dict = {"prompt": prompt, **(call.get("fixed") or {})}
        if refs:
            kwargs[call.get("images", "image")] = refs if len(refs) > 1 else refs[0]
        if call.get("steps"):
            steps = caps.get("steps") or {}
            kwargs[call["steps"]] = int(req.get("steps") or steps.get("default") or 30)
        if call.get("guidance") and req.get("guidance") is not None:
            kwargs[call["guidance"]] = float(req["guidance"])
        elif call.get("guidance") and (caps.get("guidance") or {}).get("default") is not None:
            kwargs[call["guidance"]] = float(caps["guidance"]["default"])
        if call.get("negative_prompt"):
            negative = str(req.get("negative_prompt") or "").strip() or entry.get("default_negative_prompt")
            if negative:
                kwargs[call["negative_prompt"]] = negative
        size = call.get("size")
        if (size is True or size == mode) and req.get("width") and req.get("height"):
            kwargs["width"], kwargs["height"] = int(req["width"]), int(req["height"])
        unknown = [k for k in kwargs if k not in params]
        if unknown and not any(p.kind == p.VAR_KEYWORD for p in params.values()):
            raise StudioError("CONFIG_ERROR", f"{entry['pipeline']} does not accept {', '.join(unknown)}.")
        return kwargs


# --- serving ---------------------------------------------------------------------------------------

class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline()
        if not raw:
            return
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
                    alive[0] = False

        studio: Studio = self.server.studio  # type: ignore[attr-defined]
        try:
            req = json.loads(raw)
            op = req.get("op")
            if op == "status":
                send({"status": studio.status()})
            elif op == "keep":
                studio.keep = [str(m) for m in req.get("models") or []]
                send({"ok": True})
            elif op == "check":
                send({"checks": studio.check(list(req.get("images") or []), send)})
            elif op == "generate":
                send({"done": studio.generate(req, send, lambda: alive[0])})
            else:
                send({"error": {"code": "CONFIG_ERROR", "message": f"Unknown op {op!r}"}})
        except Canceled:
            log("request canceled by the client")
        except StudioError as exc:
            send({"error": {"code": exc.code, "message": exc.message}})
        except Exception as exc:  # noqa: BLE001 - report, keep serving
            code = "GPU_OOM" if "out of memory" in str(exc).lower() else "RUNTIME_ERROR"
            log(traceback.format_exc())
            free_cuda()
            send({"error": {"code": code, "message": f"{type(exc).__name__}: {str(exc)[:300]}"}})


def free_cuda() -> None:
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None:
        with contextlib.suppress(Exception):
            torch.cuda.empty_cache()


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, path: str, studio: Studio, cfg: dict) -> None:
        self.studio = studio
        self.max_request_seconds = float(cfg.get("max_request_seconds") or 0)
        self.idle_restore_seconds = float(cfg.get("idle_restore_seconds") or 45)
        super().__init__(path, Handler)
        threading.Thread(target=self._housekeeping, daemon=True).start()

    def _housekeeping(self) -> None:
        studio = self.studio
        first, retry_at = True, 0.0
        while True:
            now = time.monotonic()
            busy = studio.busy_since
            if busy is not None and self.max_request_seconds and now - busy > self.max_request_seconds:
                log(f"a request exceeded {self.max_request_seconds:.0f}s; exiting so the supervisor restarts it")
                os._exit(70)
            idle = now - studio.last_request >= self.idle_restore_seconds
            out_of_place = set(studio.loaded) != set(studio.target()) and (first or idle) and now >= retry_at
            if out_of_place and studio.waiting == 0 and studio.gpu.acquire(blocking=False):
                try:
                    # A load that failed (e.g. another process holds the memory) is retried a minute later.
                    retry_at = 0.0 if studio.restore() else now + 60
                finally:
                    studio.gpu.release()
                    first = False
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="JSON written by the supervisor")
    with open(parser.parse_args().config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    import torch

    if not torch.cuda.is_available():
        log("no CUDA device; the studio needs a GPU")
        sys.exit(1)
    studio = Studio(cfg)
    log(f"models: {json.dumps(studio.status()['models'])}; keep: {studio.keep}")
    path = cfg["socket"]
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    server = Server(path, studio, cfg)  # serving at once; the admin's models load in the background
    os.chmod(path, 0o600)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log("ready")
    try:
        server.serve_forever()
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


if __name__ == "__main__":
    main()
