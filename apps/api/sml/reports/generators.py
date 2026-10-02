"""Report generators. Each takes a `ReportData` snapshot and returns bytes.

PDF follows the platform design language (dark header band, cyan accent, mono
labels) while staying print-friendly. HWP is produced as RTF, which Hangul
opens natively (same approach as the legacy generator).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .i18n import labels

logger = logging.getLogger(__name__)

INK = colors.HexColor("#0b0d12")
BG_BAND = colors.HexColor("#07080b")
ACCENT = colors.HexColor("#0891b2")  # print-safe cyan (the UI uses #7cf0ff on dark)
ACCENT_LIGHT = colors.HexColor("#7cf0ff")
FAKE = colors.HexColor("#d92d3f")
REAL = colors.HexColor("#16a34a")
MUTED = colors.HexColor("#5b6170")
LINE = colors.HexColor("#d9dce3")
# The company shield, white and teal for the dark header band (rendered from the logo, 266 x 300 px).
LOGO_REVERSED = Path(__file__).resolve().parent / "assets" / "logo-mark-reversed.png"

pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))


@dataclass
class ReportData:
    locale: str
    job_id: str
    run_number: int
    title: str
    media_type: str
    verdict: str
    fake_probability: float | None
    partial: bool
    ai_generated: bool  # the verdict reads "Likely AI-generated" (users never learn why)
    # Users' view only (sml.jobs.public): no detectors, metadata findings or check results.
    reasons: list[dict[str, Any]]
    analyses: list[dict[str, Any]]  # one result per analysis (face swap, AI generation)
    media: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    thumbnail: bytes | None = None
    xai_images: list[tuple[str, bytes]] = field(default_factory=list)
    explanation: str = ""


def _font(locale: str, sample: str = "") -> str:
    if locale == "ko" or any(ord(ch) > 0x2FFF for ch in sample):
        return "HYGothic-Medium"
    return "Helvetica"


def _bold(locale: str) -> str:
    return "HYGothic-Medium" if locale == "ko" else "Helvetica-Bold"


def _mono(locale: str) -> str:
    """Courier has no Hangul glyphs; Korean labels use the CID Gothic font instead."""
    return "HYGothic-Medium" if locale == "ko" else "Courier"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _verdict_text(d: ReportData, t: dict[str, str]) -> str:
    if d.ai_generated:
        return t["ai_generated"]
    return t.get(d.verdict or "inconclusive", t["inconclusive"])


def _fmt_size(n: int | None) -> str:
    if not n:
        return "—"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _analysis_text(a: dict[str, Any], t: dict[str, str]) -> str:
    if a.get("status") == "no_face":
        return t["no_face"]
    if a.get("status") != "done" or a.get("fake_probability") is None:
        return t["check_failed"]
    return f"{t.get(a.get('verdict') or 'inconclusive', t['inconclusive'])} · {_pct(a['fake_probability'])}"


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- PDF --------------------------------------------------------------------------

def render_pdf(d: ReportData) -> bytes:
    t = labels(d.locale)
    font, bold = _font(d.locale, d.title + d.explanation), _bold(d.locale)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=38 * mm,
                            bottomMargin=20 * mm, title=t["title"], author="Secure Machines Lab")
    body = ParagraphStyle("body", fontName=font, fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=MUTED)
    mono = _mono(d.locale)
    eyebrow = ParagraphStyle("eyebrow", fontName=mono, fontSize=7.5, leading=10, textColor=ACCENT,
                             spaceBefore=10, spaceAfter=4)

    def section(idx: int, name: str) -> list[Any]:
        return [Paragraph(f"{idx:03d} / {_esc(name).upper()}" if d.locale != "ko" else f"{idx:03d} / {_esc(name)}",
                          eyebrow)]

    story: list[Any] = []
    verdict_color = FAKE if d.verdict == "fake" else REAL if d.verdict == "real" else MUTED
    verdict_style = ParagraphStyle("verdict", fontName=bold, fontSize=18, leading=22, textColor=verdict_color)
    summary_cells = [
        [Paragraph(_esc(_verdict_text(d, t)), verdict_style)],
        [Paragraph(f"{t['probability']}: <b>{_pct(d.fake_probability)}</b>", body)],
    ]
    for a in d.analyses:
        name, result = _esc(t["analysis_" + a["id"]]), _esc(_analysis_text(a, t))
        summary_cells.append([Paragraph(f"{name}: <b>{result}</b>", body)])
    if d.partial:
        summary_cells.append([Paragraph(_esc(t["partial"]), small)])
    for reason in d.reasons:
        summary_cells.append([Paragraph("• " + _esc(t.get(reason.get("code", ""), reason.get("code", ""))), small)])
    left = Table(summary_cells, colWidths=[110 * mm])
    left.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    thumb_cell: Any = ""
    if d.thumbnail:
        try:
            img = ImageReader(io.BytesIO(d.thumbnail))
            iw, ih = img.getSize()
            scale = min(55 * mm / iw, 45 * mm / ih)
            thumb_cell = Image(io.BytesIO(d.thumbnail), width=iw * scale, height=ih * scale)
        except Exception:  # noqa: BLE001 - a broken thumbnail must not block the report
            thumb_cell = ""
    top = Table([[left, thumb_cell]], colWidths=[115 * mm, 59 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                             ("LINEBEFORE", (0, 0), (0, -1), 3, verdict_color),
                             ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                             ("LEFTPADDING", (0, 0), (0, -1), 10)]))
    story += [*section(1, t["verdict"]), top]

    m = d.media
    res = f"{m.get('width')}×{m.get('height')}" if m.get("width") else "—"
    info = [
        [t["file_name"], d.title], [t["type"], d.media_type], [t["size"], _fmt_size(m.get("size_bytes"))],
        [t["resolution"], res],
    ]
    if d.media_type == "video":
        info.append([t["duration"], f"{m.get('duration_seconds') or 0:.1f} s"])
    info += [[t["sha256"], m.get("sha256") or "—"], [t["job_id"], f"{d.job_id} · {t['run']} {d.run_number}"],
             [t["submitted"], d.created_at.strftime("%Y-%m-%d %H:%M UTC")],
             [t["completed"], d.finished_at.strftime("%Y-%m-%d %H:%M UTC") if d.finished_at else "—"]]
    story += [*section(2, t["file"]), _kv_table(info, font, mono)]

    if d.xai_images:
        story += section(3, t["xai"])
        cells = []
        for label, data in d.xai_images[:6]:
            try:
                img = ImageReader(io.BytesIO(data))
                iw, ih = img.getSize()
                scale = min(52 * mm / iw, 52 * mm / ih)
                cells.append([Image(io.BytesIO(data), width=iw * scale, height=ih * scale),
                              Paragraph(_esc(t.get(label, label)), small)])
            except Exception:  # skip unreadable heatmaps, keep the rest of the report
                logger.debug("Skipping unreadable artifact image %s", label, exc_info=True)
        grid = [cells[i:i + 3] for i in range(0, len(cells), 3)]
        for row in grid:
            flat = [Table([[c[0]], [c[1]]]) for c in row]
            story.append(Table([flat], colWidths=[58 * mm] * len(flat)))

    if d.explanation:
        story += section(4, t["explanation"])
        for para in d.explanation.split("\n\n")[:30]:
            story.append(Paragraph(_esc(para).replace("\n", "<br/>"), body))

    story += [Spacer(1, 8 * mm), KeepTogether([Paragraph(_esc(t["disclaimer"]), small)])]

    def on_page(canvas: Any, doc_: Any) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(BG_BAND)
        canvas.rect(0, height - 28 * mm, width, 28 * mm, stroke=0, fill=1)
        logo_h = 16 * mm
        canvas.drawImage(str(LOGO_REVERSED), width - 18 * mm - logo_h * 266 / 300, height - 14 * mm - logo_h / 2,
                         width=logo_h * 266 / 300, height=logo_h, mask="auto")
        canvas.setFillColor(ACCENT_LIGHT)
        canvas.setFont("Courier", 8)
        canvas.drawString(18 * mm, height - 11 * mm, "SML / DASH · SECURE MACHINES LAB")
        canvas.setFillColor(colors.white)
        canvas.setFont(bold, 15)
        canvas.drawString(18 * mm, height - 20 * mm, t["title"])
        canvas.setFont(font, 8.5)
        canvas.setFillColor(colors.HexColor("#9aa0ae"))
        canvas.drawString(18 * mm, height - 24.5 * mm, t["subtitle"])
        canvas.setFillColor(MUTED)
        canvas.setFont(mono, 7.5)
        canvas.drawString(18 * mm, 10 * mm, f"{t['generated']}: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · {d.job_id}")
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"{t['page']} {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _kv_table(rows: list[list[str]], font: str, mono: str) -> Table:
    style = ParagraphStyle("kv", fontName=font, fontSize=9, leading=12, textColor=INK)
    key_style = ParagraphStyle("kvk", fontName=mono, fontSize=7.5, leading=12, textColor=MUTED)
    data = [[Paragraph(_esc(str(k)).upper(), key_style), Paragraph(_esc(str(v)), style)] for k, v in rows]
    table = Table(data, colWidths=[40 * mm, 134 * mm])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return table


def _grid(rows: list[list[str]], font: str, mono: str, widths: list[float]) -> Table:
    cell = ParagraphStyle("cell", fontName=font, fontSize=8.5, leading=11, textColor=INK)
    head = ParagraphStyle("head", fontName=mono, fontSize=7.5, leading=11, textColor=colors.white)
    data = [[Paragraph(_esc(str(c)), head) for c in rows[0]]]
    data += [[Paragraph(_esc(str(c)), cell) for c in r] for r in rows[1:]]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BG_BAND), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7f9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


# --- HWP (RTF) ------------------------------------------------------------------------

def _rtf_escape(text: str) -> str:
    out = []
    for ch in text or "":
        code = ord(ch)
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\line ")
        elif code < 128:
            out.append(ch)
        else:
            signed = code if code < 32768 else code - 65536
            out.append(f"\\u{signed}?")
    return "".join(out)


def render_hwp(d: ReportData) -> bytes:
    t = labels(d.locale)
    lines = [
        r"{\rtf1\ansi\ansicpg949\deff0{\fonttbl{\f0\fnil\fcharset129 Malgun Gothic;}{\f1\fmodern Courier New;}}",
        r"{\colortbl;\red8\green145\blue178;\red217\green45\blue63;\red22\green163\blue74;\red91\green97\blue112;}",
        r"\paperw11906\paperh16838\margl1134\margr1134\margt1134\margb1134\f0\fs20",
        r"{\cf1\f1\fs16 SML / DASH \'b7 SECURE MACHINES LAB}\par",
        r"{\b\fs36 " + _rtf_escape(t["title"]) + r"}\par",
        r"{\cf4 " + _rtf_escape(t["subtitle"]) + r"}\par\par",
    ]
    color = 2 if d.verdict == "fake" else 3 if d.verdict == "real" else 4
    lines.append(r"{\b\fs28\cf" + str(color) + " " + _rtf_escape(_verdict_text(d, t)) + r"}\par")
    lines.append(_rtf_escape(f"{t['probability']}: {_pct(d.fake_probability)}") + r"\par")
    for a in d.analyses:
        lines.append(_rtf_escape(f"{t['analysis_' + a['id']]}: {_analysis_text(a, t)}") + r"\par")
    if d.partial:
        lines.append(r"{\cf4\fs16 " + _rtf_escape(t["partial"]) + r"}\par")
    lines.append(r"\par{\b " + _rtf_escape(t["file"]) + r"}\par")
    m = d.media
    for k, v in [(t["file_name"], d.title), (t["type"], d.media_type), (t["size"], _fmt_size(m.get("size_bytes"))),
                 (t["sha256"], m.get("sha256") or "—"), (t["job_id"], d.job_id)]:
        lines.append(_rtf_escape(f"{k}: {v}") + r"\par")
    if d.explanation:
        lines.append(r"\par{\b " + _rtf_escape(t["explanation"]) + r"}\par")
        lines.append(_rtf_escape(d.explanation[:20000]) + r"\par")
    lines.append(r"\par{\cf4\fs16 " + _rtf_escape(t["disclaimer"]) + r"}\par}")
    return "\n".join(lines).encode("ascii", errors="ignore")


# --- CSV / ZIP --------------------------------------------------------------------------

def render_csv(d: ReportData) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["job_id", "run", "file_name", "media_type", "verdict", "fake_probability", "partial"])
    w.writerow([d.job_id, d.run_number, d.title, d.media_type, d.verdict,
                "" if d.fake_probability is None else f"{d.fake_probability:.6f}", d.partial])
    if d.analyses:
        w.writerow([])
        w.writerow(["analysis", "verdict", "fake_probability"])
        for a in d.analyses:
            fp = a.get("fake_probability")
            w.writerow([a["id"], a.get("verdict") or a.get("status"), "" if fp is None else f"{fp:.6f}"])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens Korean correctly


def render_zip(d: ReportData, artifacts: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.pdf", render_pdf(d))
        zf.writestr("report.csv", render_csv(d))
        zf.writestr("summary.json", json.dumps({
            "job_id": d.job_id, "run": d.run_number, "file_name": d.title, "verdict": d.verdict,
            "fake_probability": d.fake_probability, "analyses": d.analyses, "reasons": d.reasons,
        }, indent=2, ensure_ascii=False, default=str))
        for name, data in artifacts:
            zf.writestr(f"artifacts/{name}", data)
    return buf.getvalue()
