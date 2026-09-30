"""A key's own rate limit can tighten the platform limit but never lift it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sml.apikeys import services
from sml.core.throttling import PrincipalRateThrottle

pytestmark = pytest.mark.django_db


def allowed_requests(key, attempts: int) -> int:  # type: ignore[no-untyped-def]
    request = SimpleNamespace(user=key.user, auth=key, META={"REMOTE_ADDR": "203.0.113.5"})
    return sum(PrincipalRateThrottle().allow_request(request, view=None) for _ in range(attempts))


def test_lower_key_limit_applies(user):
    key = services.issue_key(user, name="slow", scopes=["jobs:read"], rate_limit_per_minute=5).api_key
    assert allowed_requests(key, 10) == 5


def test_higher_key_limit_is_capped_at_the_platform_rate(user):
    platform = PrincipalRateThrottle.THROTTLE_RATES["principal"]
    limit = int(platform.split("/")[0])
    key = services.issue_key(user, name="greedy", scopes=["jobs:read"], rate_limit_per_minute=6000).api_key
    assert allowed_requests(key, limit + 20) == limit


def test_limits_are_counted_per_key(user):
    a = services.issue_key(user, name="a", scopes=["jobs:read"], rate_limit_per_minute=3).api_key
    b = services.issue_key(user, name="b", scopes=["jobs:read"], rate_limit_per_minute=3).api_key
    assert allowed_requests(a, 5) == 3
    assert allowed_requests(b, 5) == 3
