"""Debounced rate limit for inbound PAYMENT-SIGNATURE attempts (before verify/settle)."""

from __future__ import annotations

from app.config import settings
from app.ip_sliding_window import RateLimitExceeded, SlidingWindowRateLimiter


class PaymentSignatureRateLimitExceeded(RateLimitExceeded):
    """Raised when verify/settle attempts from one IP exceed the cap."""


class PaymentSignatureRateLimiter:
    def __init__(self) -> None:
        self._limiter = SlidingWindowRateLimiter(
            limit=settings.payment_signature_rate_limit_per_min,
            window_seconds=60.0,
        )

    def check(self, client_ip: str) -> None:
        if not settings.payment_signature_rate_limit_enabled:
            return
        try:
            self._limiter.check(client_ip)
        except RateLimitExceeded as exc:
            raise PaymentSignatureRateLimitExceeded(exc.retry_after) from exc


payment_signature_rate_limiter = PaymentSignatureRateLimiter()
