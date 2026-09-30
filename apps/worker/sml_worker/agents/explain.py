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


def build_prompt(context: dict[str, Any], media_name: str, xai_names: list[str], locale: str) -> str:
    summary = context.get("summary") or {}
    models = [
        {"model": m.get("name"), "fake_probability": m.get("fake_prob"), "no_face": m.get("no_face"),
         "status": m.get("status")}
        for m in summary.get("models", [])
    ]
    indicators = summary.get("ai_indicators") or {}
    return "\n".join([
        "You are a senior media-forensics analyst at Secure Machines Lab.",
        f"Write your answer in {LANG_NAMES.get(locale, 'English')}.",
        "",
        "## Task",
        "Explain to a non-expert WHY this file was judged the way it was, and whether you agree.",
        f"The file is `./{media_name}` in the current directory. Open and look at it carefully.",
        ("Explainability heatmaps (where the detectors focused) are: " + ", ".join(f"`./{n}`" for n in xai_names))
        if xai_names else "No heatmaps are available.",
        "",
        "## Automated results",
        "```json",
        json.dumps({"verdict": context.get("verdict"), "weighted_fake_probability": context.get("fake_probability"),
                    "media_type": context.get("media_type"), "models": models,
                    "metadata_indicators": {"ai_generated": indicators.get("ai_generated"),
                                            "evidence": indicators.get("evidence"),
                                            "camera": indicators.get("camera"),
                                            "software": indicators.get("software"),
                                            "c2pa_status": indicators.get("c2pa_status")}},
                   indent=2, ensure_ascii=False),
        "```",
        "",
        "## Output format (Markdown, 250–450 words)",
        "### Summary — one or two sentences: your conclusion and confidence (high/medium/low).",
        "### Visual evidence — concrete observations: skin/hair texture, eyes and teeth, lighting and shadows,",
        "  edges and blending seams, background warping, text rendering, hands, temporal flicker (video).",
        "  Refer to the heatmap regions when relevant.",
        "### Provenance — what EXIF / C2PA metadata does or doesn't show.",
        "### How the detectors agree — mention disagreements between models plainly.",
        "### Caveats — what could make this assessment wrong.",
        "",
        "Rules: be specific, never invent facts you cannot see, say 'cannot be determined' when unsure,",
        "treat detector scores as one input rather than ground truth. Do not include any preamble.",
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
