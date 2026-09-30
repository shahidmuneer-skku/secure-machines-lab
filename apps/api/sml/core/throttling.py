"""Redis-backed rate limits keyed by principal (API key, user, or IP)."""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class PrincipalRateThrottle(SimpleRateThrottle):
    """Default throttle for every endpoint.

    An API key may carry its own per-minute limit. Key owners set it themselves, so it can
    only tighten the platform rate (THROTTLE_PRINCIPAL), never raise it.
    """

    scope = "principal"

    def allow_request(self, request, view) -> bool:  # type: ignore[no-untyped-def]
        api_key = getattr(request, "auth", None)
        per_minute = getattr(api_key, "rate_limit_per_minute", None)
        if per_minute and self.num_requests and self.duration:
            platform_per_minute = self.num_requests * 60 // self.duration
            if per_minute < platform_per_minute:
                self.rate = f"{per_minute}/min"
                self.num_requests, self.duration = self.parse_rate(self.rate)
        elif not (request.user and request.user.is_authenticated):
            self.rate = self.THROTTLE_RATES.get("anon", "60/min")
            self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view) -> str:  # type: ignore[no-untyped-def]
        api_key = getattr(request, "auth", None)
        if api_key is not None and hasattr(api_key, "prefix"):
            ident = f"key:{api_key.prefix}"
        elif request.user and request.user.is_authenticated:
            ident = f"user:{request.user.pk}"
        else:
            ident = f"ip:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ScopedPrincipalThrottle(PrincipalRateThrottle):
    """Use via a subclass that sets `scope`, e.g. job creation or trial detections."""

    def allow_request(self, request, view) -> bool:  # type: ignore[no-untyped-def]
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return SimpleRateThrottle.allow_request(self, request, view)


class JobCreateThrottle(ScopedPrincipalThrottle):
    scope = "job_create"


class TrialThrottle(ScopedPrincipalThrottle):
    scope = "trial"
