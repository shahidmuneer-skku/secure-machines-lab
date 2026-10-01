"""Talks to the studio server over its Unix socket (JSON request, JSON-line events back)."""

from __future__ import annotations

import json
import socket
from collections.abc import Callable, Iterator
from typing import Any

from ..resident.supervisor import resident_dir
from . import SERVER_ID


class StudioUnavailable(Exception):
    pass


def socket_path() -> str:
    return str(resident_dir() / f"{SERVER_ID}.sock")


def stream(request: dict[str, Any], *, timeout: float | None = None,
           path: str | None = None) -> Iterator[dict[str, Any]]:
    """Send one request and yield each message the server sends back."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(path or socket_path())
    except OSError as exc:
        sock.close()
        raise StudioUnavailable(f"The studio server is not running ({exc}).") from exc
    try:
        sock.sendall((json.dumps(request) + "\n").encode())
        with sock.makefile("r", encoding="utf-8") as reader:
            for line in reader:
                if line.strip():
                    yield json.loads(line)
    finally:
        sock.close()


def call(request: dict[str, Any], *, timeout: float | None = None, path: str | None = None,
         on_event: Callable[[dict[str, Any]], None] = lambda _e: None) -> dict[str, Any]:
    """The server's final message ({"done"/"checks"/"status"/"ok"/"error": ...}); events go to on_event."""
    for message in stream(request, timeout=timeout, path=path):
        if "event" in message:
            on_event(message)
        else:
            return message
    raise StudioUnavailable("The studio server closed the connection without an answer.")
