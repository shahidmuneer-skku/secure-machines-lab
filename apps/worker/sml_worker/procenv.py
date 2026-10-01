"""The environment model subprocesses run in.

Model scripts are third-party research code, so they get an allow-listed environment (never the
platform's database, broker, payment or email secrets), their conda environment activated the
way `conda activate` would (legacy scripts call a bare `python`), per-environment extras from
`conda_envs` in config/models.yaml, and the worker's GPU.
"""

from __future__ import annotations

import os

from .config import config, gpu_env
from .registry import raw_registry

ALLOWED = {"HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TZ", "TMPDIR", "TERM", "SHELL", "CUDA_HOME",
           "CUDA_PATH", "LD_LIBRARY_PATH", "NVIDIA_DRIVER_CAPABILITIES", "NVIDIA_VISIBLE_DEVICES"}
ALLOWED_PREFIXES = ("LC_", "HF_", "HUGGINGFACE_", "TORCH_", "TRANSFORMERS_", "XDG_", "OMP_", "MKL_")
# Variables whose values are search paths: extras are prepended instead of replacing them.
SEARCH_PATHS = {"PATH", "LD_LIBRARY_PATH", "PYTHONPATH"}


def conda_env_extras(name: str) -> dict[str, str]:
    return {str(k): str(v) for k, v in ((raw_registry().get("conda_envs") or {}).get(name) or {}).items()}


def model_env(conda_env: str | None = None) -> dict[str, str]:
    c = config()
    env = {k: v for k, v in os.environ.items() if k in ALLOWED or k.startswith(ALLOWED_PREFIXES)}
    env["PATH"] = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    env.update({
        "CONDA_BIN": str(c.conda_root / "bin" / "conda"),
        "CONDA_EXE": str(c.conda_root / "bin" / "conda"),
        "FAKEDETECTOR_ROOT": str(c.models_root),
        "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:128",
        "PYTHONUNBUFFERED": "1",
    })
    env.setdefault("OMP_NUM_THREADS", "4")
    if conda_env:
        prefix = c.conda_root / "envs" / conda_env
        env["PATH"] = f"{prefix / 'bin'}{os.pathsep}{env['PATH']}"
        env["CONDA_PREFIX"] = str(prefix)
        env["CONDA_DEFAULT_ENV"] = conda_env
        for key, value in conda_env_extras(conda_env).items():
            value = value.format(env_prefix=prefix)
            if key in SEARCH_PATHS and env.get(key):
                value = f"{value}{os.pathsep}{env[key]}"
            env[key] = value
        # A conda env's OpenSSL looks for CA certificates under the prefix it was built at; an env
        # copied from another machine cannot verify any HTTPS server without this.
        certs = prefix / "ssl" / "cacert.pem"
        if "SSL_CERT_FILE" not in env and certs.is_file():
            env["SSL_CERT_FILE"] = str(certs)
    env.update(gpu_env())
    return env
