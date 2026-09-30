"""Credit prices and quotes. Prices are flat per file and do not depend on the models chosen."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from django.core.cache import cache

from .models import PriceRule

CACHE_KEY = "price-rules:v1"
Key = PriceRule.Key


def price_table() -> dict[str, int]:
    table = cache.get(CACHE_KEY)
    if table is None:
        table = {str(k): int(v) for k, v in PriceRule.DEFAULTS.items()}
        table.update({r.key: r.credits for r in PriceRule.objects.all()})
        cache.set(CACHE_KEY, table, 60)
    return table


def invalidate() -> None:
    cache.delete(CACHE_KEY)


def price(key: str) -> int:
    return price_table()[key]


@dataclass
class QuoteLine:
    label: str
    credits: int


@dataclass
class Quote:
    credits: int = 0
    lines: list[QuoteLine] = field(default_factory=list)

    def add(self, label: str, credits: int) -> None:
        self.lines.append(QuoteLine(label, credits))
        self.credits += credits


def quote_image() -> Quote:
    q = Quote()
    q.add("Image", price(Key.IMAGE))
    return q


def quote_video(duration_seconds: float) -> Quote:
    q = Quote()
    base_seconds = max(1, price(Key.VIDEO_BASE_SECONDS))
    q.add(f"Video (up to {base_seconds // 60 or 1} min)", price(Key.VIDEO_BASE))
    extra = max(0.0, float(duration_seconds) - base_seconds)
    extra_minutes = math.ceil(extra / 60) if extra > 0 else 0
    if extra_minutes:
        q.add(f"+{extra_minutes} extra minute(s)", extra_minutes * price(Key.VIDEO_PER_EXTRA_MINUTE))
    return q


def quote_long_video(duration_seconds: float) -> Quote:
    q = Quote()
    minutes = max(1, math.ceil(float(duration_seconds) / 60))
    q.add(f"Long-form video ({minutes} min)", minutes * price(Key.LONG_VIDEO_PER_MINUTE))
    return q


def quote_news() -> Quote:
    q = Quote()
    q.add("News verification case", price(Key.NEWS_CASE))
    return q


def quote_explain() -> Quote:
    q = Quote()
    q.add("Explain why (AI reasoning)", price(Key.EXPLAIN))
    return q


def quote_report(fmt: str) -> Quote:
    q = Quote()
    key = {"pdf": Key.REPORT_PDF, "hwp": Key.REPORT_HWP, "csv": Key.REPORT_CSV}[fmt]
    q.add(f"{fmt.upper()} report", price(key))
    return q


def quote_media(media_type: str, duration_seconds: float | None, module: str = "detect") -> Quote:
    if module == "long_video":
        return quote_long_video(duration_seconds or 0)
    if media_type == "image":
        return quote_image()
    return quote_video(duration_seconds or 0)
