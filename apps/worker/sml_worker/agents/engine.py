"""Agent engines for reasoning and news verification.

`openclaude` drives the local OpenClaude CLI against Ollama (media never leaves
the server); `claude` drives the Claude Code CLI with ANTHROPIC_API_KEY. Both
speak `-p --output-format stream-json`. Sessions are sandboxed exactly like the
original news app: cwd = one scratch directory, read/glob/grep scoped to it,
optional scoped Write, WebSearch/WebFetch, no Bash/Edit/MCP, no inherited settings.
`ollama` is a direct single-call vision chat (fast, no tools) used for Explain.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..config import config
from ..context import Canceled

logger = logging.getLogger(__name__)
NUM_CTX = {"qwen3.6:27b": 131072, "qwen3.8:27b-q8_0": 131072, "qwen3.8-flash-next:125b-a6b-q4_K_M": 131072,
           "qwen3-coder:480b-a35b-q2_k": 65536}


class EngineError(Exception):
    pass


def _allowed_tools(write_dir: str | None) -> list[str]:
    tools = ["WebSearch", "WebFetch", "TodoWrite", "Read(./**)", "Glob(./**)", "Grep(./**)"]
    if write_dir:
        tools.append(f"Write(./{write_dir}/**)")
    return tools


def _disallowed_tools(write_dir: str | None) -> list[str]:
    banned = ["Bash", "BashOutput", "KillShell", "Edit", "NotebookEdit", "Skill", "ExitPlanMode", "Task"]
    if not write_dir:
        banned.append("Write")
    return banned


def _describe_tool(name: str, args: dict[str, Any]) -> str:
    if name == "WebSearch":
        return f"Searching the web: {str(args.get('query', ''))[:120]}"
    if name == "WebFetch":
        return f"Reading {str(args.get('url', ''))[:140]}"
    if name in ("Read", "Glob", "Grep"):
        target = args.get("file_path") or args.get("pattern") or args.get("path") or ""
        return f"{name} {Path(str(target)).name}"[:160]
    if name == "Write":
        return f"Saving evidence {Path(str(args.get('file_path', ''))).name}"
    return f"Using {name}"


class CliAgentEngine:
    """OpenClaude (local) or Claude Code CLI, streamed."""

    def __init__(self, kind: str, model: str):
        if kind not in ("openclaude", "claude"):
            raise EngineError(f"Unknown engine {kind}")
        self.kind = kind
        self.model = model

    def _command(self) -> list[str]:
        c = config()
        if self.kind == "openclaude":
            if not Path(c.openclaude_bin).exists():
                raise EngineError(f"OpenClaude not found at {c.openclaude_bin}")
            return [c.openclaude_bin, "--provider", "ollama"]
        return ["claude", "--model", self.model]

    def _env(self) -> dict[str, str]:
        c = config()
        keep = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "SHELL", "TERM"}
        env = {k: v for k, v in os.environ.items() if k in keep}
        if self.kind == "openclaude":
            env.update({
                "CLAUDE_CODE_USE_OPENAI": "1",
                "OPENAI_BASE_URL": c.ollama_base_url.rstrip("/") + "/v1",
                "OPENAI_API_KEY": "ollama",
                "OPENAI_MODEL": self.model,
                "OPENCLAUDE_OLLAMA_NUM_CTX": str(NUM_CTX.get(self.model, 32768)),
                "API_TIMEOUT_MS": "1800000",
            })
            for key in ("TAVILY_API_KEY", "FIRECRAWL_API_KEY", "BRAVE_API_KEY", "EXA_API_KEY", "SERPAPI_API_KEY"):
                if os.environ.get(key):
                    env[key] = os.environ[key]
            if c.searxng_url and not any(env.get(k) for k in ("TAVILY_API_KEY", "FIRECRAWL_API_KEY")):
                env.update({"WEB_SEARCH_PROVIDER": "custom", "WEB_PROVIDER": "searxng",
                            "WEB_URL_TEMPLATE": c.searxng_url.rstrip("/") + "/search",
                            "WEB_PARAMS": json.dumps({"format": "json"})})
        else:
            if not c.anthropic_api_key:
                raise EngineError("ANTHROPIC_API_KEY is not configured for the Claude engine.")
            env["ANTHROPIC_API_KEY"] = c.anthropic_api_key
        return env

    def run(self, prompt: str, *, cwd: Path, write_dir: str | None, on_step: Callable[[str], None],
            check_cancel: Callable[[], None], timeout: int = 3600, max_turns: int = 60) -> str:
        if self.kind != "openclaude":
            return self._run(prompt, cwd=cwd, write_dir=write_dir, on_step=on_step, check_cancel=check_cancel,
                             timeout=timeout, max_turns=max_turns)
        from .ollama import slot

        with slot(self.model, NUM_CTX.get(self.model, 32768), on_step, check_cancel):
            return self._run(prompt, cwd=cwd, write_dir=write_dir, on_step=on_step, check_cancel=check_cancel,
                             timeout=timeout, max_turns=max_turns)

    def _run(self, prompt: str, *, cwd: Path, write_dir: str | None, on_step: Callable[[str], None],
             check_cancel: Callable[[], None], timeout: int, max_turns: int) -> str:
        argv = [
            *self._command(), "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--max-turns", str(max_turns),
            "--permission-mode", "default", "--setting-sources", "", "--strict-mcp-config",
            "--allowedTools", *_allowed_tools(write_dir), "--disallowedTools", *_disallowed_tools(write_dir),
        ]
        proc = subprocess.Popen(argv, cwd=str(cwd), env=self._env(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
        started = time.monotonic()
        final = ""
        last_text = ""
        last_beat = started
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                check_cancel()
                if time.monotonic() - started > timeout:
                    raise EngineError("The reasoning agent timed out.")
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                etype = event.get("type")
                if etype == "assistant":
                    for block in (event.get("message") or {}).get("content") or []:
                        if block.get("type") == "tool_use":
                            on_step(_describe_tool(block.get("name", ""), block.get("input") or {}))
                        elif block.get("type") == "text" and block.get("text"):
                            last_text = block["text"]
                elif etype == "result":
                    final = event.get("result") or last_text
                    if event.get("is_error"):
                        raise EngineError(str(final)[:300] or "Agent error")
                if time.monotonic() - last_beat > 30:
                    on_step(f"Still reasoning… ({int(time.monotonic() - started)}s)")
                    last_beat = time.monotonic()
        except (Canceled, EngineError):
            os.killpg(proc.pid, signal.SIGTERM)
            raise
        proc.wait(timeout=30)
        if not final and proc.returncode != 0:
            err = (proc.stderr.read() if proc.stderr else "").strip().splitlines()
            raise EngineError((err or ["Agent failed"])[-1][:300])
        return final or last_text


class OllamaVisionEngine:
    """Single-call multimodal chat against Ollama (no tools)."""

    def __init__(self, model: str):
        self.model = model

    def run(self, prompt: str, *, images: list[Path], on_step: Callable[[str], None], timeout: int = 900) -> str:
        from .ollama import slot

        with slot(self.model, NUM_CTX.get(self.model, 32768), on_step):
            return self._run(prompt, images=images, on_step=on_step, timeout=timeout)

    def _run(self, prompt: str, *, images: list[Path], on_step: Callable[[str], None], timeout: int) -> str:
        on_step(f"Asking {self.model}")
        payload = {
            "model": self.model, "stream": False, "options": {"num_ctx": NUM_CTX.get(self.model, 32768)},
            "messages": [{"role": "user", "content": prompt,
                          "images": [base64.b64encode(p.read_bytes()).decode() for p in images[:4]]}],
        }
        try:
            resp = httpx.post(config().ollama_base_url.rstrip("/") + "/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise EngineError(f"Ollama request failed: {exc}") from exc
        return (resp.json().get("message") or {}).get("content", "")
