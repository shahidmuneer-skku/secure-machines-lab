"""'Explain why' reasoning: an agent inspects the media, detector scores, XAI maps and metadata."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from ..clients import download
from ..context import TaskContext
from .engine import CliAgentEngine, OllamaVisionEngine

logger = logging.getLogger(__name__)

LANG_NAMES = {"en": "English", "ko": "Korean (한국어)", "de": "German (Deutsch)"}


ANALYSIS_NAMES = {"face_swap": "face-swap analysis", "ai_generated": "AI-generation analysis"}


def build_prompt(context: dict[str, Any], media_name: str, xai_names: list[str], locale: str) -> str:
    """The answer is shown to the user, who must not learn which detectors run or how the automated
    analysis works: the prompt carries only the combined result and the evidence users already see."""
    provenance = context.get("provenance") or {}
    checks = [{"check": c.get("id"), "status": c.get("status"), **(c.get("result") or {})}
              for c in context.get("checks") or []]
    return "\n".join([
        "You are a senior media-forensics analyst at Secure Machines Lab.",
        f"Write your answer in {LANG_NAMES.get(locale, 'English')}.",
        "",
        "## Task",
        "Explain to a non-expert WHY this file was judged the way it was, and whether you agree.",
        f"The file is `./{media_name}` in the current directory. Open and look at it carefully.",
        ("Heatmaps of the regions the automated analysis focused on are: " + ", ".join(f"`./{n}`" for n in xai_names))
        if xai_names else "No heatmaps are available.",
        "",
        "## Automated result",
        "```json",
        json.dumps({"verdict": context.get("verdict"), "fake_probability": context.get("fake_probability"),
                    "media_type": context.get("media_type"),
                    "metadata": {"ai_generation_markers": provenance.get("ai_generated"),
                                 "evidence": provenance.get("evidence"), "camera": provenance.get("camera"),
                                 "software": provenance.get("software"),
                                 "c2pa_status": provenance.get("c2pa_status")},
                    "results_by_analysis": [
                        {"analysis": ANALYSIS_NAMES.get(a.get("id"), "AI-generation analysis"),
                         "verdict": a.get("verdict"), "fake_probability": a.get("fake_probability"),
                         "status": a.get("status")}
                        for a in context.get("analyses") or []],
                    "additional_checks": checks},
                   indent=2, ensure_ascii=False),
        "```",
        "",
        "## Output format (Markdown, 250–450 words)",
        "### Summary — one or two sentences: your conclusion and confidence (high/medium/low).",
        "### Visual evidence — concrete observations: skin/hair texture, eyes and teeth, lighting and shadows,",
        "  edges and blending seams, background warping, text rendering, hands, temporal flicker (video).",
        "  Refer to the heatmap regions when relevant.",
        "### Provenance — what EXIF / C2PA metadata does or doesn't show.",
        "### Results by analysis — what the face-swap and AI-generation analyses each found,",
        "  in plain language (only those present above).",
        "### Caveats — what could make this assessment wrong.",
        "",
        "Rules: be specific, never invent facts you cannot see, say 'cannot be determined' when unsure,",
        "treat the automated result as one input rather than ground truth. Do not include any preamble.",
        "Confidential: never name or speculate about detection models, model architectures, how many",
        "detectors were used or how the automated analysis works; refer to it only as 'the automated analysis'.",
    ])


def run_explanation(envelope: dict[str, Any], ctx: TaskContext) -> str:
    media = envelope.get("media") or {}
    context = envelope.get("context") or {}
    workdir = ctx.workdir / "sandbox"
    workdir.mkdir(parents=True, exist_ok=True)
    media_name = f"media.{media.get('extension', 'bin')}"
    ctx.log("Preparing the file and heatmaps for the analyst")
    download(media["storage_key"], workdir / media_name)
    xai_names = []
    for i, art in enumerate(context.get("artifacts", [])[:6]):
        name = f"heatmap_{i + 1}{Path(art['storage_key']).suffix or '.png'}"
        try:
            download(art["storage_key"], workdir / name)
            xai_names.append(name)
        except Exception:
            logger.warning("Could not download artifact %s for explanation", art.get("storage_key"), exc_info=True)
    locale = envelope.get("locale", "en")
    prompt = build_prompt(context, media_name, xai_names, locale)
    engine_kind = envelope.get("engine", "openclaude")
    model = envelope.get("model", "qwen3.6:27b")
    ctx.progress(10, f"Reasoning with {model}", force=True)
    try:
        if engine_kind == "ollama":
            images = [workdir / media_name] if context.get("media_type") == "image" else []
            images += [workdir / n for n in xai_names]
            text = OllamaVisionEngine(model).run(prompt, images=images, on_step=ctx.log)
        else:
            text = CliAgentEngine(engine_kind, model).run(prompt, cwd=workdir, write_dir=None, on_step=ctx.log,
                                                          check_cancel=ctx.check_canceled, timeout=1800, max_turns=25)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return text.strip()
