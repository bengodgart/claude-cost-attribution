"""Tests for claude-cost-attribution. Runs against bundled fixtures only -
never against a real ~/.claude/projects directory.

Run: python -m pytest tests/ -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ccat.attribution import attribute, reconciles
from ccat.burnrate import compute_burn_rate
from ccat.parser import MAIN_SESSION, NO_SKILL, UNKNOWN_AGENT_TYPE, parse_root
from ccat.pricing import cost_for_event, load_pricing

ROOT = Path(__file__).resolve().parent.parent
PRICING_PATH = ROOT / "pricing.json"
FIXTURES = ROOT / "fixtures" / "claude_projects"
TUTOR = FIXTURES / "-P-demo-tutor"


def _pricing():
    return load_pricing(str(PRICING_PATH))


# ---------------------------------------------------------------------------
# Pricing: hand-checked cost math, with vs without cache accounting
# ---------------------------------------------------------------------------

def test_cache_aware_cost_hand_check_opus_cache_write():
    # fixture event E3: opus, input 5000, cache_creation_1h 10000, output 1000
    # with_cache = (5000*5 + 10000*5*2.0 + 1000*25) / 1e6 = 150000/1e6
    breakdown = cost_for_event(_pricing(), "claude-opus-4-8", 5000, 10000, 0, 0, 1000)
    assert breakdown.matched_model is True
    assert breakdown.with_cache == pytest.approx(0.15, rel=1e-9)


def test_naive_cost_hand_check_sonnet_cache_read():
    # fixture event E2: sonnet, input 2000, cache_read 8000, output 100
    # with_cache    = (2000*3 + 8000*3*0.1 + 100*15) / 1e6 = 9900/1e6 = 0.0099
    # without_cache = ((2000+8000)*3 + 100*15) / 1e6      = 31500/1e6 = 0.0315
    breakdown = cost_for_event(_pricing(), "claude-sonnet-4-5", 2000, 0, 0, 8000, 100)
    assert breakdown.with_cache == pytest.approx(0.0099, rel=1e-9)
    assert breakdown.without_cache == pytest.approx(0.0315, rel=1e-9)
    assert breakdown.without_cache > breakdown.with_cache


def test_unmatched_model_falls_back_to_default_rate_not_an_error():
    breakdown = cost_for_event(_pricing(), "some-future-model-nobody-added-yet", 1000, 0, 0, 0, 100)
    assert breakdown.matched_model is False
    assert breakdown.with_cache > 0


# ---------------------------------------------------------------------------
# Parsing: discovers the main transcript and both subagent runs
# ---------------------------------------------------------------------------

def test_parse_root_finds_session_and_subagents():
    result = parse_root(TUTOR)
    assert result.sessions_seen == 1
    assert result.subagent_runs_seen == 2
    assert not result.warnings  # both .meta.json sidecars are present and valid


def test_missing_meta_json_is_flagged_not_silently_dropped(tmp_path):
    project = tmp_path / "-P-orphan"
    project.mkdir()
    main = project / "session-x.jsonl"
    main.write_text(
        '{"type":"user","cwd":"C:\\\\orphan","sessionId":"session-x","timestamp":"2026-06-01T00:00:00Z","message":{"role":"user","content":[]}}\n',
        encoding="utf-8",
    )
    subdir = project / "session-x" / "subagents"
    subdir.mkdir(parents=True)
    agent_file = subdir / "agent-orphan1.jsonl"
    agent_file.write_text(
        '{"type":"assistant","cwd":"C:\\\\orphan","sessionId":"session-x","timestamp":"2026-06-01T00:01:00Z",'
        '"message":{"role":"assistant","model":"claude-sonnet-4-5","content":[],'
        '"usage":{"input_tokens":100,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":10}}}\n',
        encoding="utf-8",
    )
    # deliberately no agent-orphan1.meta.json

    result = parse_root(tmp_path)
    assert result.subagent_runs_seen == 1
    assert any("meta.json" in w for w in result.warnings)
    unknown_events = [e for e in result.events if e.agent_type == UNKNOWN_AGENT_TYPE]
    assert len(unknown_events) == 1


# ---------------------------------------------------------------------------
# Attribution: per-skill and per-subagent splits reconcile to the total,
# with explicit "(no skill)" / "(main session, no subagent)" buckets - no
# signal is silently dropped.
# ---------------------------------------------------------------------------

def test_cache_aware_total_matches_manual_sum_of_all_events():
    # manual sum of every assistant usage line in the -P-demo-tutor fixture
    # (main transcript E1..E6 + both subagent events), computed by hand in
    # EVIDENCE.md against the same pricing.json rates.
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    assert a.total.with_cache == pytest.approx(0.3438, rel=1e-6)


def test_main_session_and_subagent_sums_match_hand_check():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    main_only = sum(pe.with_cache for pe in a.priced_events if pe.event.source == "main")
    subagent_only = sum(pe.with_cache for pe in a.priced_events if pe.event.source == "subagent")
    assert main_only == pytest.approx(0.2762, rel=1e-6)
    assert subagent_only == pytest.approx(0.0676, rel=1e-6)
    assert main_only + subagent_only == pytest.approx(a.total.with_cache, rel=1e-9)


def test_per_skill_split_reconciles_to_total_no_lost_tokens():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    assert reconciles(a.total, a.by_skill)
    assert NO_SKILL in a.by_skill
    assert "generate-guide" in a.by_skill
    assert "pretty-guide" in a.by_skill
    assert a.by_skill[NO_SKILL].with_cache == pytest.approx(0.115, rel=1e-6)
    assert a.by_skill["generate-guide"].with_cache == pytest.approx(0.206, rel=1e-6)
    assert a.by_skill["pretty-guide"].with_cache == pytest.approx(0.0228, rel=1e-6)


def test_per_subagent_split_reconciles_to_total_no_lost_tokens():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    assert reconciles(a.total, a.by_agent_type)
    assert MAIN_SESSION in a.by_agent_type
    assert "executor" in a.by_agent_type
    assert "general-purpose" in a.by_agent_type
    assert a.by_agent_type["executor"].with_cache == pytest.approx(0.0625, rel=1e-6)
    assert a.by_agent_type["general-purpose"].with_cache == pytest.approx(0.0051, rel=1e-6)


def test_per_project_split_reconciles_across_multiple_projects():
    result = parse_root(FIXTURES)
    a = attribute(result.events, _pricing())
    assert reconciles(a.total, a.by_project)
    assert len(a.by_project) == 2
    tutor_bucket = a.by_project["C:\\Users\\demo\\dev\\demo-tutor-app"]
    other_bucket = a.by_project["C:\\Users\\demo\\dev\\demo-other-app"]
    assert tutor_bucket.with_cache == pytest.approx(0.3438, rel=1e-6)
    assert other_bucket.with_cache == pytest.approx(0.00855, rel=1e-6)


# ---------------------------------------------------------------------------
# Burn-rate: rolling 7-day window vs a user-supplied weekly cap
# ---------------------------------------------------------------------------

def test_burn_rate_window_includes_all_fixture_events():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    burn = compute_burn_rate(a.priced_events, weekly_cap=1.0)
    # latest event is 2026-06-06T14:05:00Z; every fixture event falls inside
    # the trailing 7 days from there, so the window total equals the grand total
    assert burn.weekly_cost == pytest.approx(a.total.with_cache, rel=1e-6)
    assert burn.pct_of_cap == pytest.approx(burn.weekly_cost / 1.0, rel=1e-6)
    assert burn.days_to_cap is not None
    assert burn.days_to_cap > 0


def test_burn_rate_without_a_cap_omits_projection():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    burn = compute_burn_rate(a.priced_events, weekly_cap=None)
    assert burn.pct_of_cap is None
    assert burn.days_to_cap is None
    assert burn.weekly_cost > 0


def test_burn_rate_flags_cap_already_exceeded():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    tiny_cap = a.total.with_cache / 10  # already 10x over
    burn = compute_burn_rate(a.priced_events, weekly_cap=tiny_cap)
    assert burn.pct_of_cap > 1.0
    assert burn.days_to_cap < burn.days_elapsed


def test_burn_rate_with_no_timestamps_does_not_crash():
    result = parse_root(TUTOR)
    a = attribute(result.events, _pricing())
    for pe in a.priced_events:
        pe.event.timestamp = None
    burn = compute_burn_rate(a.priced_events, weekly_cap=1.0)
    assert burn.window_end is None
    assert burn.weekly_cost == 0.0
    assert burn.events_without_timestamp == len(a.priced_events)
