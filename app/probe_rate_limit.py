"""Per-IP rate limiter for GET /probe (10 requests per minute)."""

from __future__ import annotations

from app.ip_sliding_window import RateLimitExceeded, SlidingWindowRateLimiter


class ProbeRateLimitExceeded(Exception):
    """Raised when a client exceeds the probe rate limit."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Probe rate limit exceeded; retry after {retry_after}s")


class ProbeRateLimiter:
    """In-memory sliding window: max 10 probes per minute per client IP."""

    def __init__(self, *, limit: int = 10, window_seconds: float = 60.0) -> None:
        self._limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)

    def check(self, client_ip: str) -> None:
        try:
            self._limiter.check(client_ip)
        except RateLimitExceeded as exc:
            raise ProbeRateLimitExceeded(exc.retry_after) from exc


probe_rate_limiter = ProbeRateLimiter()