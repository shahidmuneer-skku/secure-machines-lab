"""EXIEF metadata signals in the metadata step (owner, 2026-10-01).

EXIEF scores what ExifTool reads; the API weighs its verdict into the AI-generation analysis.
Metadata the file itself shows to be damaged or altered is reported as untrustworthy.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from sml_worker.adapters import metadata

# The tags ExifTool reads from an OpenAI gpt-image PNG with Content Credentials (trimmed).
OPENAI_PNG = {
    "SourceFile": "ai.png", "File:FileName": "ai.png", "File:FileType": "PNG", "File:MIMEType": "image/png",
    "Composite:ImageSize": "1122x1402",
    "JUMBF:ActionsDigitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "JUMBF:ActionsSoftwareAgentName": "gpt-image",
    "JUMBF:Claim_Generator_InfoName": "OpenAI Media Service API",
}
CAMERA_JPEG = {"SourceFile": "photo.jpg", "File:FileName": "photo.jpg", "File:FileType": "JPEG",
               "Composite:ImageSize": "4032x3024", "EXIF:Make": "Apple", "EXIF:Model": "iPhone 15",
               "EXIF:ThumbnailLength": 9000}


@pytest.fixture
def png(tmp_path: Path) -> Path:
    path = tmp_path / "a.png"
    Image.new("RGB", (8, 8), "white").save(path)
    return path


def fake_tools(monkeypatch: pytest.MonkeyPatch, record: dict[str, Any] | None, c2pa: dict[str, Any] | None = None):
    read = (lambda path: (record, "ok")) if record else (lambda path: (None, "tool_unavailable"))
    monkeypatch.setattr(metadata, "_read_exiftool", read)
    monkeypatch.setattr(metadata, "_read_c2pa", lambda path: c2pa or {"status": "none"})


def test_a_generator_declaration_is_confirmed_and_named(monkeypatch, png):
    fake_tools(monkeypatch, OPENAI_PNG, {"status": "valid", "untrusted_signer": True, "failures": []})
    report = metadata.analyze(png, "image")
    ex = report["exief"]
    assert (ex["status"], ex["verdict"], ex["generator"], ex["untrustworthy"]) == (
        "ok", "confirmed", "OpenAI Media Service API", [])
    assert "c2pa_trained" in [s["id"] for s in ex["signals"]]
    assert report["ai_generated"] and report["confidence"] == "strong"
    assert report["evidence"] == [{"source": "Generator declaration", "strength": "strong",
                                   "detail": "C2PA trainedAlgorithmicMedia — OpenAI Media Service API"}]


def test_no_signal_shows_no_evidence(monkeypatch, png):
    fake_tools(monkeypatch, CAMERA_JPEG)
    report = metadata.analyze(png, "image")
    assert report["exief"]["verdict"] == "unknown" and report["evidence"] == [] and not report["ai_generated"]


@pytest.mark.parametrize(("extra", "c2pa", "reason"), [
    ({"ExifTool:Warning": "Truncated PNG image"}, None, "ExifTool: Truncated PNG image"),
    ({"ExifTool:Error": "File format error"}, None, "ExifTool: File format error"),
    ({}, {"status": "invalid_signature", "failures": ["assertion.dataHash.mismatch"]},
     "C2PA manifest failed validation (assertion.dataHash.mismatch)"),
])
def test_damaged_or_altered_metadata_is_not_trusted(monkeypatch, png, extra, c2pa, reason):
    fake_tools(monkeypatch, {**OPENAI_PNG, **extra}, c2pa)
    report = metadata.analyze(png, "image")
    assert report["exief"]["untrustworthy"] == [reason]
    assert not report["ai_generated"] and report["confidence"] == "none"
    assert any("not counted" in n for n in report["notes"])


def test_minor_warnings_and_the_idat_signal_are_not_damage(monkeypatch, png):
    fake_tools(monkeypatch, {**OPENAI_PNG, "ExifTool:Warning": [
        "[minor] Fixed incorrect URI for xmlns", "Text/EXIF chunk(s) found after PNG IDAT (may be ignored)"]})
    assert metadata.analyze(png, "image")["exief"]["untrustworthy"] == []


def test_without_exiftool_the_builtin_checks_still_run(monkeypatch, png):
    fake_tools(monkeypatch, None, {"status": "valid", "ai_source_types": ["trainedalgorithmicmedia"],
                                   "generator": "Adobe Firefly"})
    report = metadata.analyze(png, "image")
    assert report["exief"] == {"status": "tool_unavailable"} and report["ai_generated"]


@pytest.mark.parametrize(("payload", "status", "failures"), [
    # OpenAI's signer is not on c2patool's trust list, but the manifest is intact.
    ({"validation_state": "Valid", "validation_status": [{"code": "signingCredential.untrusted"}]}, "valid", []),
    ({"validation_state": "Invalid", "validation_status": [{"code": "assertion.dataHash.mismatch"}],
      "validation_results": {"activeManifest": {"failure": [{"code": "assertion.dataHash.mismatch"}]}}},
     "invalid_signature", ["assertion.dataHash.mismatch"]),
])
def test_c2pa_state(monkeypatch, png, payload, status, failures):
    monkeypatch.setattr(metadata, "_c2patool", lambda: "c2patool")
    out = json.dumps({"active_manifest": "m", "manifests": {"m": {"claim_generator": "x"}}, **payload})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    c2pa = metadata._read_c2pa(png)
    assert (c2pa["status"], c2pa["failures"]) == (status, failures)


def test_a_damaged_image_still_gets_a_report(monkeypatch, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    fake_tools(monkeypatch, {**OPENAI_PNG, "ExifTool:Warning": "Truncated PNG image"})
    report = metadata.analyze(broken, "image")
    assert report["exief"]["untrustworthy"] and any("damaged" in n for n in report["notes"])
