"""Keeps the detection workflow out of text written by language models (owner, 2026-10-02).

Users must not learn which detectors run, how many or how they work, whether a file's metadata
(EXIF / XMP / IPTC / C2PA) is read, or which extra checks run. Prompts never give the models those
facts; this is the second line of defence: any sentence of a model's answer that mentions them, or
that describes what the analysis looks for, is dropped before the answer is stored or shown. It
covers English, Korean and German, the platform's languages, and the names of every detector in the
catalog.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

# Terms that describe how the analysis works. Matched case-insensitively.
_TERMS = [
    # metadata and provenance
    r"meta[\s-]?data", r"exif", r"xmp", r"iptc", r"c2pa", r"content[\s-]credentials?", r"provenance",
    r"camera\s+(?:make|model|maker|brand|tags?|fingerprints?|signatures?|traces?)",
    r"software\s+(?:tags?|fields?|signatures?)", r"(?:file|image|video)\s+(?:properties|headers?|tags)",
    r"embedded\s+(?:data|information|tags|markers)", r"generation\s+(?:markers?|parameters)",
    # detectors and the way they work
    r"detectors?", r"classifiers?", r"ensembles?", r"anti[\s-]?spoof(?:ing)?", r"liveness", r"nsfw",
    r"face\s+detect(?:ion|ors?)", r"grad[\s-]?cam", r"saliency", r"prnu",
    r"sensor\s+(?:noise|fingerprints?|patterns?)",
    r"frequency\s+(?:analysis|domain|spectrum|fingerprints?|artifacts?)",
    r"(?:detection|forensic)\s+models?", r"exief", r"centaur",
    # how a verdict follows from a probability
    r"thresholds?", r"cut[\s-]?offs?",
    r"(?:below|above|under|over|exceeds?|exceeding|(?:greater|less|more|higher|lower)\s+than)\s+\d{1,3}(?:\.\d+)?\s?%",
    r"center\s+(?:models?|detectors?)", r"effort[\s·-]+(?:deepfake|ai[\s-]?gen)",
    # the language model behind the assistant
    r"qwen", r"ollama", r"openclaude",
]
# Korean and German (no word boundaries for Hangul).
_TERMS_NO_BOUNDARY = [
    "메타데이터", "메타 데이터", "촬영 정보", "카메라 정보", "콘텐츠 자격", "출처 정보", "임계값", "임곗값",
    "탐지기", "검출기", "탐지 모델",
    "분류기", "앙상블", "위변조 방지", "라이브니스", "얼굴 탐지", "얼굴 검출",
    "metadaten", "inhaltsnachweis", "herkunftsnachweis", "detektor", "klassifikator", "erkennungsmodell",
    "lebenderkennung", "schwellenwert",
]
# Detector names that are also everyday words; they are covered by the context patterns above.
_GENERIC_NAMES = {"center", "effort"}

# Sentences that say what the analysis does rather than what it found ("the system checked for odd
# textures", "the model looks for lighting errors"): models are told not to speculate about the method,
# and this catches them when they do. Outcomes ("the analysis found no signs of manipulation") and
# advice to the user ("you can look for…", "use tools to check whether…") are kept. English only.
_SUBJECT = r"(?:system|analys[ie]s|models?|detectors?|algorithms?|tools?|software|engine|scanner|ai)"
_CUES = (r"(?:texture|lighting|light|shadow|edge|pixel|noise|frequenc|compression|blend|boundar|skin|colou?r"
         r"|artifact|artefact|pattern|inconsistenc)\w*")
_MECHANISM = (
    rf"\b{_SUBJECT}\s+(?:(?!to\b)\w+\s+)?"
    r"(?:(?:check|look|search|scan|test)(?:s|ed|es|ned)?\s+(?:\w+ly\s+)?(?:for|whether|if)\b"
    r"|rel(?:y|ies|ied)\s+on\b"
    rf"|(?:examin|inspect|measur|analy[sz]|compar)(?:e|es|ed|ing)?\s+(?:(?:the|its|their)\s+)?{_CUES})"
)


def _catalog_names() -> tuple[str, ...] | None:
    """Detector and long-form model names from the catalog (ids, display names, legacy ids), or None
    when the catalog cannot be read right now."""
    try:
        from sml.catalog.registry import registry

        reg = registry()
    except Exception:  # noqa: BLE001 - the filter must work even if the catalog cannot be read
        return None
    names: set[str] = set()
    specs: list[Any] = [*reg.models.values(), *reg.long_video_models.values()]
    for spec in specs:
        names.add(spec.id)
        names.update(getattr(spec, "legacy_ids", []) or [])
        names.update(str(v) for v in (getattr(spec, "display_name", {}) or {}).values())
    kept = {n.strip() for n in names if n and n.strip().lower() not in _GENERIC_NAMES}
    return tuple(sorted(kept, key=len, reverse=True))


@lru_cache(maxsize=2)
def _compile(names: tuple[str, ...]) -> re.Pattern[str]:
    escaped = [re.escape(n).replace(" ", r"\s+") for n in names]
    bounded = "|".join([*_TERMS, *escaped])
    loose = "|".join(re.escape(t) for t in _TERMS_NO_BOUNDARY)
    return re.compile(rf"(?<![\w-])(?:{bounded})(?![\w-])|{loose}|{_MECHANISM}", re.IGNORECASE)


_names: tuple[str, ...] | None = None


def _pattern() -> re.Pattern[str]:
    """The catalog's names are read once they are available (the generic terms always apply)."""
    global _names
    if _names is None:
        _names = _catalog_names()
    return _compile(_names or ())


def mentions_method(text: str) -> bool:
    return bool(_pattern().search(text))


_SENTENCE_END = re.compile(r"(?<=[.!?。])\s+|(?<=다\.)\s*|(?<=요\.)\s*")


def _sentences(line: str) -> list[str]:
    parts = [p for p in _SENTENCE_END.split(line) if p]
    return parts or [line]


def scrub(text: str) -> str:
    """Removes every sentence (and any bullet or heading left empty) that mentions the method."""
    if not text or not mentions_method(text):
        return text
    out: list[str] = []
    for line in text.split("\n"):
        if not mentions_method(line):
            out.append(line)
            continue
        prefix = re.match(r"^\s*(?:[-*•]|\d+[.)]|#{1,6})\s+", line)
        lead = prefix.group(0) if prefix else ""
        body = line[len(lead):]
        kept = [s for s in _sentences(body) if not mentions_method(s)]
        if kept and not lead.lstrip().startswith("#"):
            out.append(lead + " ".join(k.strip() for k in kept))
        # a heading that names the method goes entirely, as does a bullet with nothing left
    return drop_empty_sections("\n".join(out)).strip()


# A Markdown heading, or a line that is bold only (the way chat models often write headings).
_HEADING = re.compile(r"^\s*(?:#{1,6}\s|(?:\*\*|__)[^*_].*(?:\*\*|__):?\s*$)")


def drop_empty_sections(text: str) -> str:
    """Removes headings left with nothing under them (their sentences were withheld)."""
    lines = text.split("\n")
    keep: list[str] = []
    for i, line in enumerate(lines):
        if _HEADING.match(line):
            rest = next((ln for ln in lines[i + 1:] if ln.strip()), "")
            if not rest or _HEADING.match(rest):
                continue
        keep.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(keep))


class StreamGuard:
    """Filters a streamed answer sentence by sentence: text is released once a sentence is complete
    and clean; sentences that mention the method are dropped."""

    def __init__(self) -> None:
        self._buf = ""
        self.dropped = 0

    def feed(self, chunk: str) -> Iterator[str]:
        self._buf += chunk
        while True:
            m = re.search(r"[.!?。](?=\s)|\n", self._buf)
            if not m:
                return
            end = m.end()
            sentence, self._buf = self._buf[:end], self._buf[end:]
            yield from self._release(sentence)

    def flush(self) -> Iterator[str]:
        rest, self._buf = self._buf, ""
        if rest:
            yield from self._release(rest)

    def _release(self, sentence: str) -> Iterator[str]:
        if mentions_method(sentence):
            self.dropped += 1
            # keep the line break so markdown structure survives
            if sentence.endswith("\n"):
                yield "\n"
            return
        yield sentence
