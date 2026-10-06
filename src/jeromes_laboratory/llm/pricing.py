"""Dated, exact-model Standard API rates for *planning* estimates only.

These rates do not change historical call records. Unknown aliases, providers,
service tiers, or account-specific premiums deliberately remain unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

CAPTURED_ON = "2026-10-05"


@dataclass(frozen=True)
class TextRate:
    input_per_million_usd: float
    cached_input_per_million_usd: float
    output_per_million_usd: float
    source_url: str
    captured_on: str = CAPTURED_ON


_RATES: dict[str, TextRate] = {
    "gpt-6-astra": TextRate(10.0, 1.0, 50.0, "https://developers.openai.com/api/docs/models/gpt-6-astra"),
    "gpt-6.1-sol": TextRate(2.0, 0.10, 10.0, "https://developers.openai.com/api/docs/models/gpt-6.1-sol"),
    "gpt-6-sol": TextRate(2.0, 0.20, 10.0, "https://developers.openai.com/api/docs/models/gpt-6-sol", "2026-10-06"),
    "gpt-6-luna": TextRate(0.10, 0.01, 0.50, "https://developers.openai.com/api/docs/models/gpt-6-luna"),
    "gpt-5.6-sol": TextRate(4.0, 0.40, 20.0, "https://developers.openai.com/api/docs/models/gpt-5.6-sol"),
    "gpt-5.6-terra": TextRate(2.0, 0.20, 12.0, "https://developers.openai.com/api/docs/models/gpt-5.6-terra"),
    "gpt-5.6-luna": TextRate(0.20, 0.02, 1.20, "https://developers.openai.com/api/docs/models/gpt-5.6-luna"),
    "gpt-5.5": TextRate(5.0, 0.50, 30.0, "https://developers.openai.com/api/docs/models/gpt-5.5"),
    "gpt-5.4-nano": TextRate(0.20, 0.02, 1.25, "https://developers.openai.com/api/docs/models/gpt-5.4-nano"),
}


def estimate_standard_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int,
    cached_input_tokens: int = 0, *, aggregate_batches: bool = False,
) -> dict[str, object]:
    if (
        provider != "openai" or model not in _RATES or input_tokens < 0
        or output_tokens < 0 or cached_input_tokens < 0
        or cached_input_tokens > input_tokens
        or (input_tokens > 272_000 and not aggregate_batches)
    ):
        return {"status": "unavailable", "usd": None, "source_url": None,
                "captured_on": None}
    rate = _RATES[model]
    amount = (
        (input_tokens - cached_input_tokens) * rate.input_per_million_usd
        + cached_input_tokens * rate.cached_input_per_million_usd
        + output_tokens * rate.output_per_million_usd
    ) / 1_000_000
    return {
        "status": "estimated", "usd": round(amount, 9),
        "source_url": rate.source_url, "captured_on": rate.captured_on,
        "input_per_million_usd": rate.input_per_million_usd,
        "cached_input_per_million_usd": rate.cached_input_per_million_usd,
        "output_per_million_usd": rate.output_per_million_usd,
    }
