"""Aggregate UsageEvents into cost buckets: total, per-project, per-skill,
per-subagent. Every split is a full partition of the same events, so each
one reconciles exactly to the grand total - there is no bucket that quietly
absorbs tokens the other views do not account for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .parser import UsageEvent
from .pricing import PricingConfig, cost_for_event


@dataclass
class Bucket:
    label: str
    with_cache: float = 0.0
    without_cache: float = 0.0
    input_tokens: int = 0
    cache_creation_1h: int = 0
    cache_creation_5m: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    event_count: int = 0

    def add(self, event: UsageEvent, cost_with: float, cost_without: float) -> None:
        self.with_cache += cost_with
        self.without_cache += cost_without
        self.input_tokens += event.input_tokens
        self.cache_creation_1h += event.cache_creation_1h
        self.cache_creation_5m += event.cache_creation_5m
        self.cache_read_tokens += event.cache_read_tokens
        self.output_tokens += event.output_tokens
        self.event_count += 1

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_1h
            + self.cache_creation_5m
            + self.cache_read_tokens
            + self.output_tokens
        )


@dataclass
class CostEvent:
    """An UsageEvent with its priced cost attached, kept for burn-rate math."""

    event: UsageEvent
    with_cache: float
    without_cache: float


@dataclass
class Attribution:
    total: Bucket
    by_project: dict
    by_skill: dict
    by_agent_type: dict
    unmatched_models: set
    priced_events: list


def attribute(events: list, pricing: PricingConfig) -> Attribution:
    total = Bucket(label="TOTAL")
    by_project: dict = {}
    by_skill: dict = {}
    by_agent_type: dict = {}
    unmatched_models: set = set()
    priced_events: list = []

    for event in events:
        breakdown = cost_for_event(
            pricing,
            event.model,
            event.input_tokens,
            event.cache_creation_1h,
            event.cache_creation_5m,
            event.cache_read_tokens,
            event.output_tokens,
        )
        if not breakdown.matched_model:
            unmatched_models.add(event.model or "(no model recorded)")

        total.add(event, breakdown.with_cache, breakdown.without_cache)
        by_project.setdefault(event.project, Bucket(label=event.project)).add(
            event, breakdown.with_cache, breakdown.without_cache
        )
        by_skill.setdefault(event.skill, Bucket(label=event.skill)).add(
            event, breakdown.with_cache, breakdown.without_cache
        )
        by_agent_type.setdefault(event.agent_type, Bucket(label=event.agent_type)).add(
            event, breakdown.with_cache, breakdown.without_cache
        )
        priced_events.append(CostEvent(event=event, with_cache=breakdown.with_cache, without_cache=breakdown.without_cache))

    return Attribution(
        total=total,
        by_project=by_project,
        by_skill=by_skill,
        by_agent_type=by_agent_type,
        unmatched_models=unmatched_models,
        priced_events=priced_events,
    )


def reconciles(total: Bucket, split: dict, tolerance: float = 1e-9) -> bool:
    """True if a split's bucket costs sum back to the total (no lost tokens)."""
    return abs(sum(b.with_cache for b in split.values()) - total.with_cache) <= tolerance
