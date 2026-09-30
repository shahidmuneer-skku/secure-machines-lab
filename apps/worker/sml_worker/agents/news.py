"""Multimedia news verification (MV26 workflow), ported from the Veritas desktop app.

One sandboxed agent run per case: skill + instructions + rubric + few-shot
reports, then the case metadata, staged media and Secure Machines Lab detector
results. The agent must return a report starting with '# Case Summary' and a
final ```json``` block with the verdict metadata.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..clients import download
from ..context import TaskContext
from .engine import CliAgentEngine

ASSETS = Path(__file__).parent / "assets" / "news"
REPORT_SKELETON = """# Case Summary
[STATUS]. <concise overview: what is claimed, what is verified, what remains unconfirmed — highlight uncertainties.>

# Content Classification
- **Tags:** <platforms, people, organizations, locations, topics>

# Verified Evidence
- **Source Details:** <origin URLs, original post, watermark/channel attribution, publication chain>
- **Where? (Location):** <City/Area, Region, Country; decimal coordinates; geolocation method>
- **When? (Time):** <date or range; how established>
- **Who? (Entities Involved):** <people, units, organizations>
- **Why? (Motivation or Intent):** <propaganda/information-warfare context; who benefits>

# Forensic Analysis
- **Authenticity Assessment:** <Original / Modified / Recaptured / Synthetic — with reasoning>
- **Verification Tools & Methods:** <tools and techniques used>
- **Synthetic Type (if applicable):** <GAN / Stable Diffusion / Other — or N/A>
- **Other Artifacts:** <anomalies, metadata/compression inconsistencies, discontinuities>

# Other Evidence & Findings
- **Supporting Sources:** <numbered references>
- **Cross-Checking Information:** <how findings were validated across independent sources>
- **Other info:** <additional context>"""

LANG_NAMES = {"en": "English", "ko": "Korean (한국어)", "de": "German (Deutsch)"}


def _read(name: str) -> str:
    path = ASSETS / name
    return path.read_text() if path.exists() else ""


def _few_shots(limit: int = 3) -> str:
    blocks = []
    for case in sorted((ASSETS / "fewshot").glob("*"))[:limit]:
        blocks.append("\n".join([f"## Example {case.name}", "### Input", "```json",
                                 (case / "input.json").read_text().strip(), "```", "### Target report.md",
                                 (case / "report.md").read_text().strip()]))
    return "\n\n---\n\n".join(blocks)


def build_prompt(case: dict[str, Any], media_names: list[tuple[str, str]], forensics: list[dict[str, Any]],
                 locale: str) -> str:
    forensic_lines = []
    for f in forensics:
        if f.get("fake_prob") is None:
            state = "no face" if f.get("no_face") else f.get("status", "n/a")
            forensic_lines.append(f"- {f.get('file')}: model {f.get('model')} → {state}")
        else:
            forensic_lines.append(f"- {f.get('file')}: model {f.get('model')} → fake probability "
                                  f"{float(f['fake_prob']) * 100:.1f}%")
    return "\n".join([
        "# YOUR SKILL", _read("skill.md"), "", "# TASK INSTRUCTIONS", _read("instructions.md"), "",
        "# SCORING RUBRIC", _read("evaluation.md"), "",
        "# FEW-SHOT EXAMPLES (input JSON → target report.md)", _few_shots(), "", "---", "",
        "# VERIFICATION REQUEST", "", "## Case metadata", "```json", json.dumps(case, indent=2, ensure_ascii=False),
        "```", "", "## Attached media (in the current directory)",
        "\n".join(f"- [{kind}] ./{name}" for name, kind in media_names) or "(none)", "",
        "## Pre-computed forensic detection (Secure Machines Lab)",
        "\n".join(forensic_lines) or "(no detector results)", "",
        "Treat detector results as ONE input — decide authenticity yourself and explain disagreements.",
        f"Write the report in {LANG_NAMES.get(locale, 'English')} (keep the section headings in English).",
        "", "Silently run the full verification workflow from your skill. Do NOT narrate your process.",
        'CRITICAL OUTPUT RULE: begin with exactly "# Case Summary" and nothing before it.',
        "Fill EVERY section; where evidence is insufficient write the finding plus Indeterminate / "
        "Inconclusive / Not Feasible.", "", REPORT_SKELETON, "",
        "After the report output ONE final ```json``` block with keys: status, confidence (0-100), coordinates "
        "{lat, lng, label}, tags, when, who, authenticity {verdict: real|fake|uncertain, confidence 0-100, "
        "reasoning}, sources [{title, url, date}], annotations [{claim, verdict: supported|refuted|unverified, "
        "source, date}]. Output nothing after this block.",
    ])


def parse_output(text: str) -> tuple[str, dict[str, Any]]:
    start = text.find("# Case Summary")
    body = text[start:] if start >= 0 else text
    meta: dict[str, Any] = {}
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", body, re.S)
    if blocks:
        try:
            meta = json.loads(blocks[-1])
        except ValueError:
            meta = {}
        body = body[: body.rfind("```json")].rstrip()
    return body.strip(), meta


def run_news(envelope: dict[str, Any], case: dict[str, Any], media: list[dict[str, Any]],
             ctx: TaskContext) -> dict[str, Any]:
    sandbox = ctx.workdir / "case"
    sandbox.mkdir(parents=True, exist_ok=True)
    names: list[tuple[str, str]] = []
    for i, m in enumerate(media):
        name = f"media_{i + 1}.{m.get('extension', 'bin')}"
        download(m["storage_key"], sandbox / name)
        names.append((name, m.get("media_type", "image")))
    options = envelope.get("options") or {}
    engine = options.get("engine", "openclaude")
    model = options.get("model", "qwen3.6:27b")
    prompt = build_prompt(case, names, envelope.get("forensics") or [], envelope.get("locale", "en"))
    ctx.log(f"Verification agent started ({engine} · {model}); this can take several minutes")
    ctx.progress(8, "Researching sources", force=True)
    try:
        text = CliAgentEngine(engine, model).run(prompt, cwd=sandbox, write_dir=None, on_step=ctx.log,
                                                 check_cancel=ctx.check_canceled, timeout=3 * 3600, max_turns=80)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    report, meta = parse_output(text)
    if not report.startswith("# Case Summary"):
        ctx.log("Warning: the agent did not follow the report format exactly")
    return {"report_markdown": report, "meta": meta}
