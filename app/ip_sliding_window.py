"""Shared per-IP sliding-window rate limiter for HTTP guards."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """In-memory sliding window: ``limit`` events per ``window_seconds`` per IP."""

    def __init__(self, *, limit: int, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_ip: str) -> int:
        """Record one event for ``client_ip`` or raise ``RateLimitExceeded``.

        Returns remaining capacity in the current window after recording.
        """
        now = time.time()
        window = self._windows[client_ip]
        cutoff = now - self._window
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= self._limit:
            retry_after = max(int(self._window - (now - window[0])), 1)
            raise RateLimitExceeded(retry_after)

        window.append(now)
        return max(self._limit - len(window), 0)


class RateLimitExceeded(Exception):
    """Raised when a client exceeds a sliding-window cap."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded; retry after {retry_after}s")
