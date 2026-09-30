"""Adapter contract shared by every model integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..context import TaskContext


class AdapterError(Exception):
    """A classified failure. `code` drives retries (see API results.RETRYABLE_CODES)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ModelResult:
    fake_prob: float | None = None
    label: str = ""
    no_face: bool = False
    faces: list[dict[str, Any]] = field(default_factory=list)
    per_frame: list[dict[str, Any]] = field(default_factory=list)
    intervals: list[dict[str, Any]] = field(default_factory=list)
    fallback: dict[str, Any] | None = None
    simulated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"fake_prob": self.fake_prob, "no_face": self.no_face, "simulated": self.simulated}
        if self.label:
            out["label"] = self.label
        if self.faces:
            out["faces"] = self.faces
        if self.per_frame:
            out["per_frame"] = self.per_frame[-2000:]
        if self.intervals:
            out["intervals"] = self.intervals
        if self.fallback:
            out["fallback"] = self.fallback
        out.update(self.extra)
        return out


class ModelAdapter(Protocol):
    id: str

    def run(self, media_path: Path, media_type: str, ctx: TaskContext) -> ModelResult: ...
