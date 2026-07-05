"""Cache-aware cost math, priced from an editable local config file.

Why cache-aware matters: a raw "input tokens x price" estimate is wrong for
Claude Code, because most turns are dominated by prompt-cache traffic, not
fresh input. `cache_creation_input_tokens` costs MORE than a fresh input
token (you are paying to write the cache), and `cache_read_input_tokens`
costs much LESS (a 90% discount on a cache hit). Treating everything as
plain input tokens over- or under-states the bill depending on the mix.

This module computes cost two ways for every usage event, so the gap is
visible:
    - with_cache:    the accurate price, using the multipliers below.
    - without_cache: the naive price, as if cache write/read tokens were
                      billed as plain fresh input (what a tool that ignores
                      caching would report).

Pricing itself lives in pricing.json (repo root), not in this file, so a
price change never needs a code change or a network call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_PRICING: dict = {
    "cache_write_1h_multiplier": 2.0,
    "cache_write_5m_multiplier": 1.25,
    "cache_read_multiplier": 0.1,
    "models": [
        {"name": "opus", "match": ["opus"], "input": 5.0, "output": 25.0},
        {"name": "sonnet", "match": ["sonnet"], "input": 3.0, "output": 15.0},
        {"name": "haiku", "match": ["haiku"], "input": 1.0, "output": 5.0},
    ],
    "default_model": {"name": "unmatched", "input": 3.0, "output": 15.0},
}


def repo_root_pricing_path() -> Path:
    """Default location: pricing.json at the repo root (one level above ccat/)."""
    return Path(__file__).resolve().parent.parent / "pricing.json"


@dataclass
class ModelRate:
    name: str
    input: float
    output: float


@dataclass
class PricingConfig:
    cache_write_1h_multiplier: float
    cache_write_5m_multiplier: float
    cache_read_multiplier: float
    models: list
    default_model: ModelRate
    source: str

    def rate_for(self, model_id: Optional[str]) -> tuple[ModelRate, bool]:
        """Return (rate, matched). matched=False means the fallback default was used."""
        if model_id:
            low = model_id.lower()
            for m in self.models:
                if any(tok in low for tok in m["match"]):
                    return ModelRate(m["name"], m["input"], m["output"]), True
        return self.default_model, False


def load_pricing(path: Optional[str] = None) -> PricingConfig:
    """Load pricing config from `path`, or the repo-root pricing.json, or the
    built-in fallback if neither file is present (e.g. an installed copy with
    no repo checkout)."""
    candidate = Path(path) if path else repo_root_pricing_path()
    raw = DEFAULT_PRICING
    source = "built-in fallback (no pricing.json found)"
    if candidate.is_file():
        with open(candidate, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        source = path if path else "pricing.json (repo root)"
    default_model = ModelRate(
        raw["default_model"]["name"], raw["default_model"]["input"], raw["default_model"]["output"]
    )
    return PricingConfig(
        cache_write_1h_multiplier=raw["cache_write_1h_multiplier"],
        cache_write_5m_multiplier=raw["cache_write_5m_multiplier"],
        cache_read_multiplier=raw["cache_read_multiplier"],
        models=raw["models"],
        default_model=default_model,
        source=source,
    )


@dataclass
class CostBreakdown:
    with_cache: float
    without_cache: float
    matched_model: bool


def cost_for_event(
    pricing: PricingConfig,
    model_id: Optional[str],
    input_tokens: int,
    cache_creation_1h: int,
    cache_creation_5m: int,
    cache_read_tokens: int,
    output_tokens: int,
) -> CostBreakdown:
    rate, matched = pricing.rate_for(model_id)
    per_tok = 1.0 / 1_000_000.0

    with_cache = (
        input_tokens * rate.input
        + cache_creation_1h * rate.input * pricing.cache_write_1h_multiplier
        + cache_creation_5m * rate.input * pricing.cache_write_5m_multiplier
        + cache_read_tokens * rate.input * pricing.cache_read_multiplier
        + output_tokens * rate.output
    ) * per_tok

    without_cache = (
        (input_tokens + cache_creation_1h + cache_creation_5m + cache_read_tokens) * rate.input
        + output_tokens * rate.output
    ) * per_tok

    return CostBreakdown(with_cache=with_cache, without_cache=without_cache, matched_model=matched)
