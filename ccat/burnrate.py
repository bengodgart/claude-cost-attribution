"""Burn-rate gauge: rolling spend vs a configurable weekly cap.

The cap is supplied by the user (a CLI flag), never scraped from Anthropic -
there is no API for a Pro/Max plan's usage limits, so this is a self-declared
budget line, not a live plan reading.

Window: the trailing 7 days ending at the latest event timestamp in the
data (not "now" - a fixture or an old export should not silently claim to be
current). `days_elapsed` is floored at one hour so a small/fast fixture does
not divide by a near-zero span.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

MIN_DAYS_ELAPSED = 1.0 / 24.0  # one hour floor


@dataclass
class BurnRate:
    weekly_cap: Optional[float]
    window_start: Optional[object]
    window_end: Optional[object]
    weekly_cost: float
    days_elapsed: float
    daily_rate: float
    pct_of_cap: Optional[float]
    days_to_cap: Optional[float]
    events_without_timestamp: int


def compute_burn_rate(priced_events: list, weekly_cap: Optional[float]) -> BurnRate:
    timed = [pe for pe in priced_events if pe.event.timestamp is not None]
    missing = len(priced_events) - len(timed)

    if not timed:
        return BurnRate(
            weekly_cap=weekly_cap,
            window_start=None,
            window_end=None,
            weekly_cost=0.0,
            days_elapsed=0.0,
            daily_rate=0.0,
            pct_of_cap=None,
            days_to_cap=None,
            events_without_timestamp=missing,
        )

    window_end = max(pe.event.timestamp for pe in timed)
    window_start = window_end - timedelta(days=7)
    in_window = [pe for pe in timed if pe.event.timestamp >= window_start]

    weekly_cost = sum(pe.with_cache for pe in in_window)
    earliest_in_window = min(pe.event.timestamp for pe in in_window)
    days_elapsed = max((window_end - earliest_in_window).total_seconds() / 86400.0, MIN_DAYS_ELAPSED)
    daily_rate = weekly_cost / days_elapsed

    pct_of_cap = (weekly_cost / weekly_cap) if weekly_cap else None
    days_to_cap = (weekly_cap / daily_rate) if (weekly_cap and daily_rate > 0) else None

    return BurnRate(
        weekly_cap=weekly_cap,
        window_start=window_start,
        window_end=window_end,
        weekly_cost=weekly_cost,
        days_elapsed=days_elapsed,
        daily_rate=daily_rate,
        pct_of_cap=pct_of_cap,
        days_to_cap=days_to_cap,
        events_without_timestamp=missing,
    )
