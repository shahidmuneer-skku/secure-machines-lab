"""Flat per-file prices (owner-approved defaults) and admin overrides."""

from __future__ import annotations

import pytest

from sml.credits import pricing
from sml.credits.models import PriceRule

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(("seconds", "expected"), [
    (5, 10), (60, 10), (61, 15), (120, 15), (121, 20), (600, 55),
])
def test_video_price_is_base_plus_each_started_extra_minute(seconds, expected):
    assert pricing.quote_video(seconds).credits == expected


@pytest.mark.parametrize(("seconds", "expected"), [(10, 4), (60, 4), (61, 8), (3600, 240)])
def test_long_video_is_charged_per_started_minute(seconds, expected):
    assert pricing.quote_long_video(seconds).credits == expected


def test_other_prices():
    assert pricing.quote_image().credits == 1
    assert pricing.quote_news().credits == 15
    assert pricing.quote_explain().credits == 3
    assert pricing.quote_report("pdf").credits == 0


def test_admin_price_change_applies_after_cache_invalidation():
    PriceRule.objects.filter(key=PriceRule.Key.IMAGE).update(credits=2)
    pricing.invalidate()
    assert pricing.quote_media("image", None).credits == 2
