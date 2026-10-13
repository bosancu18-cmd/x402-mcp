"""DevSecOps guards: payment-signature debounce, buyer caps, provenance meta."""

from __future__ import annotations

import pytest
from app.buyer_spend_guard import BuyerSpendCapExceeded, assert_pay_and_fetch_allowed
from app.config import settings
from app.ip_sliding_window import RateLimitExceeded, SlidingWindowRateLimiter
from app.payment_signature_rate_limit import payment_signature_rate_limiter


def test_sliding_window_rate_limiter_blocks_after_cap() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60.0)
    limiter.check("1.2.3.4")
    limiter.check("1.2.3.4")
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("1.2.3.4")
    assert exc.value.retry_after >= 1


def test_payment_signature_rate_limiter_enforces_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "payment_signature_rate_limit_enabled", True)
    payment_signature_rate_limiter._limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60.0)
    payment_signature_rate_limiter.check("203.0.113.1")
    from app.payment_signature_rate_limit import PaymentSignatureRateLimitExceeded

    with pytest.raises(PaymentSignatureRateLimitExceeded):
        payment_signature_rate_limiter.check("203.0.113.1")


def test_meta_envelope_includes_authorship() -> None:
    from app.commerce import InMemoryQuotaStore

    store = InMemoryQuotaStore()
    snapshot = store.consume_quota("provenance-agent")
    meta = store.build_meta(snapshot)
    assert meta.authorship.project == "x402-mcp"
    assert meta.authorship.license == "Apache-2.0"
    assert "github.com" in meta.authorship.repository


def test_buyer_spend_guard_blocks_when_over_daily_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(settings, "buyer_spend_policy_enforced", True)
    monkeypatch.setattr(settings, "evm_private_key", "0x" + "11" * 32)
    from app import ledger_io

    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "policy.json").write_text(
        '{"max_price_per_call_usdc": 1.0, "daily_cap_usdc": 0.01, "monthly_cap_usdc": 10.0}',
        encoding="utf-8",
    )
    spend = ledger_dir / "spend.jsonl"
    spend.write_text(
        '{"ts": "2026-10-13T12:00:00+00:00", "amount_usdc": 0.01, "settled": true}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ledger_io, "LEDGER", ledger_dir)

    with pytest.raises(BuyerSpendCapExceeded):
        assert_pay_and_fetch_allowed(
            url="https://example.com/paid",
            max_price_usdc=0.05,
            preferred_network="eip155:84532",
        )
