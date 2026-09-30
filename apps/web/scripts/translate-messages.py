#!/usr/bin/env python3
"""Translate messages/en.json → ko.json / de.json with the local Ollama model (data never leaves the server).

Every translated string is validated: identical {placeholders}, ICU plural/select structure and <rich> tags.
Strings that fail validation after retries fall back to English and are listed in the report.

Usage: python3 scripts/translate-messages.py [--model qwen3.8:27b-q8_0] [--only ko|de] [--missing-only]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "messages"
OLLAMA = "http://127.0.0.1:11434/api/chat"

GLOSSARY = {
    "ko": ("credits=크레딧, job=작업, detection=탐지, deepfake=딥페이크, verdict=판정, result(s)=결과, model=모델, queue=대기열, "
           "worker=워커, audit chain=감사 체인, API key=API 키, subscription=구독, plan=요금제, credit pack=크레딧 팩, dashboard=대시보드, "
           "report=보고서, sign in=로그인, sign up/create account=회원가입, two-factor authentication=2단계 인증, passkey=패스키, "
           "recovery code=복구 코드, session=세션, admin=관리자, role=역할, capability=권한, refund=환불, ledger=원장, "
           "news verification=뉴스 검증, long-form video=장편 영상, explainability=설명 가능성, provenance=출처, metadata=메타데이터"),
    "de": ("credits=Credits, job=Auftrag, detection=Erkennung, deepfake=Deepfake, verdict=Ergebnis, results=Ergebnisse, model=Modell, "
           "queue=Warteschlange, worker=Worker, audit chain=Prüfkette, API key=API-Schlüssel, subscription=Abo, plan=Tarif, "
           "credit pack=Credit-Paket, dashboard=Dashboard, report=Bericht, sign in=Anmelden, sign up=Registrieren, "
           "two-factor authentication=Zwei-Faktor-Authentifizierung, passkey=Passkey, recovery code=Wiederherstellungscode, "
           "session=Sitzung, admin=Admin, role=Rolle, refund=Erstattung, ledger=Credit-Verlauf, news verification=Nachrichtenprüfung, "
           "long-form video=Langvideo, explainability=Erklärbarkeit, provenance=Herkunft. Use the formal 'Sie'."),
}
LANG_NAME = {"ko": "Korean", "de": "German"}
KEEP = "SML, DASH, Secure Machines Lab, Toss Payments, Stripe, API, EXIF, XMP, C2PA, XAI, Grad-CAM, TOTP, PDF, HWP, CSV, ZIP, JSON, KST, GPU, VRAM, OpenClaude, Qwen, Ollama, Claude, IP, CIDR, RabbitMQ"

TAG = re.compile(r"</?([a-zA-Z]+)>")


def icu_structure(text: str) -> list[str]:
    """Arguments, their types and plural/select selectors, in order (branch text is ignored)."""
    out: list[str] = []

    def message(i: int) -> int:
        while i < len(text):
            ch = text[i]
            if ch == "{":
                i = argument(i + 1)
            elif ch == "}":
                return i
            else:
                i += 1
        return i

    def argument(i: int) -> int:
        j = i
        while j < len(text) and text[j] not in ",}":
            j += 1
        out.append("arg:" + text[i:j].strip())
        if j >= len(text) or text[j] == "}":
            return j + 1
        k = j + 1
        while k < len(text) and text[k] not in ",}":
            k += 1
        kind = text[j + 1:k].strip()
        out.append("type:" + kind)
        if k >= len(text) or text[k] == "}":
            return k + 1
        i = k + 1
        if kind not in ("plural", "select", "selectordinal"):
            depth = 1
            while i < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            return i
        while i < len(text):
            while i < len(text) and text[i].isspace():
                i += 1
            if i < len(text) and text[i] == "}":
                return i + 1
            j = i
            while j < len(text) and text[j] != "{":
                j += 1
            out.append("sel:" + text[i:j].strip())
            i = message(j + 1) + 1
        return i

    message(0)
    return out


def flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def unflatten(flat: dict[str, str]) -> dict:
    root: dict = {}
    for key, value in flat.items():
        node = root
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    return root


def signature(text: str) -> tuple:
    return (sorted(icu_structure(text)), sorted(TAG.findall(text)), text.count("{"), text.count("}"),
            text.count("#") > 0)


def ask(model: str, lang: str, chunk: dict[str, str]) -> dict[str, str]:
    system = (
        f"You are a professional software localizer translating UI strings of a deepfake-detection web app into {LANG_NAME[lang]}. "
        "Return ONLY a JSON object with exactly the same keys and translated values. Rules: keep every {placeholder} exactly; "
        "in ICU messages like '{count, plural, one {# credit} other {# credits}}' keep the structure, keywords (plural, one, other, =0) "
        "and '#' unchanged and translate only the human text inside the braces; keep <tag>…</tag> markers and translate the text between them; "
        f"do not translate these terms: {KEEP}. Keep punctuation style natural for the language, keep it concise for UI. "
        f"Glossary: {GLOSSARY[lang]}."
    )
    body = json.dumps({
        "model": model, "stream": False, "format": "json", "think": False,
        "options": {"temperature": 0.1, "num_ctx": 32768},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps(chunk, ensure_ascii=False, indent=1)}],
    }).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        content = json.loads(resp.read())["message"]["content"]
    return json.loads(content)


def translate(model: str, lang: str, missing_only: bool) -> None:
    en = flatten(json.loads((ROOT / "en.json").read_text()))
    target_path = ROOT / f"{lang}.json"
    existing = flatten(json.loads(target_path.read_text())) if target_path.exists() else {}
    todo = {k: v for k, v in en.items() if not (missing_only and k in existing and existing[k] != v)}
    result = {k: existing.get(k, v) for k, v in en.items()}
    keys = list(todo)
    failed: list[str] = []
    size = 40
    for i in range(0, len(keys), size):
        chunk = {k: todo[k] for k in keys[i:i + size]}
        pending = dict(chunk)
        for attempt in range(3):
            if not pending:
                break
            try:
                out = ask(model, lang, pending)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{lang}] chunk {i // size} attempt {attempt + 1} error: {exc}", file=sys.stderr)
                continue
            for k in list(pending):
                value = out.get(k)
                if isinstance(value, str) and value.strip() and signature(value) == signature(pending[k]):
                    result[k] = value
                    del pending[k]
        failed.extend(pending)
        print(f"[{lang}] {min(i + size, len(keys))}/{len(keys)} done, {len(failed)} fallbacks", flush=True)
        target_path.write_text(json.dumps(unflatten(result), indent=2, ensure_ascii=False) + "\n")
    report = ROOT.parent / f"scripts/translation-report-{lang}.txt"
    report.write_text("\n".join(failed) + "\n")
    print(f"[{lang}] finished: {len(keys) - len(failed)} translated, {len(failed)} left in English (see {report.name})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3.8:27b-q8_0")
    parser.add_argument("--only", choices=["ko", "de"])
    parser.add_argument("--missing-only", action="store_true", help="Only translate keys still identical to English")
    args = parser.parse_args()
    for lang in [args.only] if args.only else ["ko", "de"]:
        translate(args.model, lang, args.missing_only)


if __name__ == "__main__":
    main()
