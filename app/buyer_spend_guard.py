"""Enforce ledger/policy.json caps before outbound pay_and_fetch spends."""

from __future__ import annotations

from app.config import settings
from app.swarm.policy import load_policy, review_purchase, spend_totals


class BuyerSpendCapExceeded(ValueError):
    """Raised when a purchase would breach configured daily/monthly caps."""


def assert_pay_and_fetch_allowed(
    *,
    url: str,
    max_price_usdc: float | None,
    preferred_network: str | None,
) -> None:
    """Veto pay_and_fetch when policy enforcement is on and caps would break."""
    if not settings.buyer_spend_policy_enforced:
        return
    if not settings.evm_private_key and not settings.svm_private_key:
        return

    policy = load_policy()
    spent_today, spent_month = spend_totals()
    price = max_price_usdc if max_price_usdc is not None else policy.max_price_per_call_usdc
    reason = review_purchase(
        policy,
        url=url,
        price_usdc=price,
        network=preferred_network,
        spent_today=spent_today,
        spent_month=spent_month,
    )
    if reason:
        raise BuyerSpendCapExceeded(reason)
