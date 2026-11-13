"""Estimated cost of a Muse call from provider-reported token counts.

Prices per 1M tokens, standard mode, prompts under 200K tokens, from
https://dev.meta.ai/docs/pricing-rate-limits (read 2026-11-13). Estimates for
budget tracking only; the provider's bill is authoritative. Reasoning tokens
are billed as output tokens and are already included in outputTokens.
"""
from __future__ import annotations

PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-wonder-1.0": (4.00, 20.00),
    "muse-ember-1.0": (0.10, 0.50),
}


def estimate_cost_usd(model: str | None, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """None when the model has no listed price or counts are missing."""
    prices = PRICES_USD_PER_MTOK.get(model or "")
    if prices is None or input_tokens is None or output_tokens is None:
        return None
    return round((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000, 6)
