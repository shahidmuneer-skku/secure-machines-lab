"""'Explain why' reasoning: a vision model looks at the media and the heatmaps and explains the result."""

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


CONFIDENTIAL_RULE = (
    "STRICTLY CONFIDENTIAL: never mention, hint at or speculate about how the result was obtained — no "
    "detectors, models, model names or architectures, no number of analyses or checks, no scores per method; "
    "nothing about the file's metadata (EXIF, XMP, IPTC, C2PA, content credentials, camera or software "
    "information, embedded data, file properties); no face-detection, content-safety or anti-spoofing checks. "
    "Refer to the process only as 'the analysis'. If something cannot be explained without these, leave it out."
)


def build_prompt(context: dict[str, Any], media_name: str, xai_names: list[str], locale: str) -> str:
    """The answer is shown to the user, who must not learn how the analysis works (owner, 2026-10-01 and
    2026-10-02): the prompt carries only the result as users see it — no detectors, metadata or checks."""
    results = [{"analysis": ANALYSIS_NAMES.get(a.get("id"), "AI-generation analysis"), "verdict": a.get("verdict"),
                "fake_probability": a.get("fake_probability"), "status": a.get("status")}
               for a in context.get("analyses") or []]
    return "\n".join([
        "You are a media-forensics analyst at Secure Machines Lab, writing for a non-expert.",
        f"Write your answer in {LANG_NAMES.get(locale, 'English')}.",
        "",
        "## Task",
        "Explain what the analysis result means for this file and which visible details are consistent with it.",
        f"The file is `./{media_name}` in the current directory. Look at it carefully.",
        ("Heatmaps of the regions the analysis focused on are: " + ", ".join(f"`./{n}`" for n in xai_names))
        if xai_names else "No heatmaps are available.",
        "",
        "## Analysis result (final)",
        "```json",
        json.dumps({"verdict": context.get("verdict_label") or context.get("verdict"),
                    "fake_probability": context.get("fake_probability"), "media_type": context.get("media_type"),
                    "no_face_found": bool(context.get("no_face")), "results_by_analysis": results},
                   indent=2, ensure_ascii=False),
        "```",
        "",
        "## Output format (Markdown, 200–400 words)",
        "### Summary — one or two sentences: what the result says, in plain words.",
        "### What is visible — concrete observations consistent with the result: skin/hair texture, eyes and",
        "  teeth, lighting and shadows, edges and blending, background, text, hands, flicker (video).",
        "  Refer to the highlighted heatmap regions when relevant.",
        "### Results by analysis — what the face-swap and AI-generation analyses found, in plain language",
        "  (only those present above).",
        "### Caveats — general limits (image quality, compression, small or partly hidden faces).",
        "",
        "Rules: be specific, never invent facts you cannot see, say 'cannot be determined' when unsure.",
        "The analysis result is final: never contradict or second-guess it. Do not include any preamble.",
        CONFIDENTIAL_RULE,
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
