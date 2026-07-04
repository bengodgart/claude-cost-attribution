"""Render a cost-attribution Report to text, Markdown, or self-contained dark HTML."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Optional

from .attribution import Attribution, reconciles
from .burnrate import BurnRate
from .parser import ParseResult

BAR_WIDTH = 28


@dataclass
class Report:
    root: str
    parsed: ParseResult
    attribution: Attribution
    burn: BurnRate
    pricing_source: str
    top_n: int = 10


def _bar(share: float) -> str:
    share = max(0.0, min(1.0, share))
    filled = int(round(share * BAR_WIDTH))
    return "#" * filled + "-" * (BAR_WIDTH - filled)


def _money(x: float) -> str:
    return f"${x:,.4f}"


def _sorted_buckets(split: dict, top_n: Optional[int] = None):
    items = sorted(split.values(), key=lambda b: b.with_cache, reverse=True)
    return items[:top_n] if top_n else items


def render_text(report: Report) -> str:
    a = report.attribution
    total = a.total.with_cache or 1e-12
    lines: list = []

    lines.append("Claude Code cost attribution")
    lines.append(f"root: {report.root}")
    lines.append(f"pricing: {report.pricing_source}")
    lines.append(
        f"sessions parsed: {report.parsed.sessions_seen}   subagent runs: {report.parsed.subagent_runs_seen}"
    )
    lines.append("")

    delta = a.total.without_cache - a.total.with_cache
    delta_pct = (delta / total) * 100 if total else 0.0
    lines.append(f"TOTAL cost, cache-aware:       {_money(a.total.with_cache)}")
    lines.append(f"TOTAL cost, naive (no cache):  {_money(a.total.without_cache)}  ({delta_pct:+.0f}% vs cache-aware)")
    lines.append(
        f"  input {a.total.input_tokens:,}  cache-write-1h {a.total.cache_creation_1h:,}  "
        f"cache-write-5m {a.total.cache_creation_5m:,}  cache-read {a.total.cache_read_tokens:,}  "
        f"output {a.total.output_tokens:,}"
    )
    lines.append("")

    lines.append("Cost by project")
    for b in _sorted_buckets(a.by_project):
        share = b.with_cache / total
        lines.append(f"  {_money(b.with_cache):>12}  {share:>5.0%}  [{_bar(share)}]  {b.label}  ({b.event_count} turns)")
    lines.append("")

    lines.append("Cost by skill (heuristic span: active from the turn after a Skill call to the next one)")
    for b in _sorted_buckets(a.by_skill):
        share = b.with_cache / total
        lines.append(f"  {_money(b.with_cache):>12}  {share:>5.0%}  [{_bar(share)}]  {b.label}")
    lines.append(f"  reconciles to total: {'yes' if reconciles(a.total, a.by_skill) else 'no'}")
    lines.append("")

    lines.append("Cost by subagent (agentType from .meta.json - hard signal, not heuristic)")
    for b in _sorted_buckets(a.by_agent_type):
        share = b.with_cache / total
        lines.append(f"  {_money(b.with_cache):>12}  {share:>5.0%}  [{_bar(share)}]  {b.label}")
    lines.append(f"  reconciles to total: {'yes' if reconciles(a.total, a.by_agent_type) else 'no'}")
    lines.append("")

    burn = report.burn
    lines.append("Burn-rate gauge")
    if burn.window_end is None:
        lines.append("  no timestamped events found - cannot compute a burn rate")
    else:
        lines.append(f"  trailing 7-day window: {burn.window_start} to {burn.window_end}")
        lines.append(f"  spend in window: {_money(burn.weekly_cost)}")
        lines.append(f"  daily rate: {_money(burn.daily_rate)}/day (over {burn.days_elapsed:.2f} elapsed days)")
        if burn.weekly_cap:
            pct = burn.pct_of_cap * 100 if burn.pct_of_cap is not None else 0.0
            lines.append(f"  weekly cap: {_money(burn.weekly_cap)} (user-supplied)  -  {pct:.0f}% of cap used")
            if burn.days_to_cap is not None:
                lines.append(f"  at the current daily rate: cap reached in {burn.days_to_cap:.1f} days")
            else:
                lines.append("  at the current daily rate: no burn observed, cap not projected to be reached")
        else:
            lines.append("  no --weekly-cap given - pass one to see percent-of-cap and days-to-cap")
    if burn.events_without_timestamp:
        lines.append(f"  ({burn.events_without_timestamp} turn(s) had no parsable timestamp and were excluded from the window)")
    lines.append("")

    if a.unmatched_models:
        lines.append("Unmatched models (priced at the pricing.json default_model fallback - add an exact match to price them precisely):")
        for m in sorted(a.unmatched_models):
            lines.append(f"  - {m}")
        lines.append("")

    if report.parsed.warnings:
        lines.append(f"Warnings ({len(report.parsed.warnings)}):")
        for w in report.parsed.warnings[:20]:
            lines.append(f"  - {w}")
        if len(report.parsed.warnings) > 20:
            lines.append(f"  ... and {len(report.parsed.warnings) - 20} more")

    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    a = report.attribution
    total = a.total.with_cache or 1e-12
    md: list = []

    md.append("# Claude Code cost attribution")
    md.append("")
    md.append(f"**Root:** `{report.root}`  ")
    md.append(f"**Pricing:** `{report.pricing_source}`  ")
    md.append(f"**Sessions parsed:** {report.parsed.sessions_seen} &middot; **Subagent runs:** {report.parsed.subagent_runs_seen}")
    md.append("")

    delta = a.total.without_cache - a.total.with_cache
    delta_pct = (delta / total) * 100 if total else 0.0
    md.append(f"**TOTAL cost, cache-aware:** {_money(a.total.with_cache)}  ")
    md.append(f"**TOTAL cost, naive (no cache accounting):** {_money(a.total.without_cache)} ({delta_pct:+.0f}% vs cache-aware)")
    md.append("")

    md.append("## Cost by project")
    md.append("")
    md.append("| Cost | Share | Project | Turns |")
    md.append("|---|---|---|---|")
    for b in _sorted_buckets(a.by_project):
        md.append(f"| {_money(b.with_cache)} | {b.with_cache/total:.0%} | {b.label} | {b.event_count} |")
    md.append("")

    md.append("## Cost by skill")
    md.append("")
    md.append("_Heuristic span: active from the turn after a Skill call to the next one._")
    md.append("")
    md.append("| Cost | Share | Skill |")
    md.append("|---|---|---|")
    for b in _sorted_buckets(a.by_skill):
        md.append(f"| {_money(b.with_cache)} | {b.with_cache/total:.0%} | {b.label} |")
    md.append(f"\nReconciles to total: **{'yes' if reconciles(a.total, a.by_skill) else 'no'}**")
    md.append("")

    md.append("## Cost by subagent")
    md.append("")
    md.append("_`agentType` from `.meta.json` - a hard signal, not a heuristic._")
    md.append("")
    md.append("| Cost | Share | Subagent |")
    md.append("|---|---|---|")
    for b in _sorted_buckets(a.by_agent_type):
        md.append(f"| {_money(b.with_cache)} | {b.with_cache/total:.0%} | {b.label} |")
    md.append(f"\nReconciles to total: **{'yes' if reconciles(a.total, a.by_agent_type) else 'no'}**")
    md.append("")

    burn = report.burn
    md.append("## Burn-rate gauge")
    md.append("")
    if burn.window_end is None:
        md.append("No timestamped events found.")
    else:
        md.append(f"- Trailing 7-day window: `{burn.window_start}` to `{burn.window_end}`")
        md.append(f"- Spend in window: {_money(burn.weekly_cost)}")
        md.append(f"- Daily rate: {_money(burn.daily_rate)}/day (over {burn.days_elapsed:.2f} elapsed days)")
        if burn.weekly_cap:
            pct = burn.pct_of_cap * 100 if burn.pct_of_cap is not None else 0.0
            md.append(f"- Weekly cap: {_money(burn.weekly_cap)} (user-supplied) - {pct:.0f}% used")
            if burn.days_to_cap is not None:
                md.append(f"- At the current daily rate: cap reached in {burn.days_to_cap:.1f} days")
        else:
            md.append("- No `--weekly-cap` given.")
    md.append("")

    if a.unmatched_models:
        md.append("## Unmatched models")
        md.append("")
        for m in sorted(a.unmatched_models):
            md.append(f"- `{m}`")
        md.append("")

    return "\n".join(md)


def render_html(report: Report) -> str:
    a = report.attribution
    total = a.total.with_cache or 1e-12

    def rows(split, extra_col=None):
        out = ""
        for b in _sorted_buckets(split):
            share = b.with_cache / total
            pct = f"{share:.0%}"
            extra = f"<td class='num'>{b.event_count}</td>" if extra_col else ""
            out += (
                f"<tr><td class='num'>{_money(b.with_cache)}</td>"
                f"<td class='barcell'><div class='bar'><div class='fill' style='width:{share*100:.1f}%'></div></div><span class='pct'>{pct}</span></td>"
                f"<td>{html.escape(b.label)}</td>{extra}</tr>"
            )
        return out

    delta = a.total.without_cache - a.total.with_cache
    delta_pct = (delta / total) * 100 if total else 0.0

    burn = report.burn
    if burn.window_end is None:
        burn_html = "<p class='sub'>No timestamped events found - cannot compute a burn rate.</p>"
    else:
        cap_html = ""
        if burn.weekly_cap:
            pct = (burn.pct_of_cap or 0) * 100
            cap_html = f"<div class='metric'><span class='mlbl'>weekly cap</span><span class='mval'>{_money(burn.weekly_cap)} ({pct:.0f}% used)</span></div>"
            if burn.days_to_cap is not None:
                cap_html += f"<div class='metric'><span class='mlbl'>days to cap at current rate</span><span class='mval'>{burn.days_to_cap:.1f}</span></div>"
        else:
            cap_html = "<p class='sub'>No --weekly-cap given.</p>"
        burn_html = (
            f"<div class='metric'><span class='mlbl'>window</span><span class='mval'>{html.escape(str(burn.window_start))} &rarr; {html.escape(str(burn.window_end))}</span></div>"
            f"<div class='metric'><span class='mlbl'>spend in window</span><span class='mval'>{_money(burn.weekly_cost)}</span></div>"
            f"<div class='metric'><span class='mlbl'>daily rate</span><span class='mval'>{_money(burn.daily_rate)}/day</span></div>"
            f"{cap_html}"
        )

    unmatched_html = ""
    if a.unmatched_models:
        items = "".join(f"<li><code>{html.escape(m)}</code></li>" for m in sorted(a.unmatched_models))
        unmatched_html = f"<h2>Unmatched models</h2><p class='sub'>Priced at the pricing.json fallback rate. Add an exact match to price precisely.</p><ul>{items}</ul>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code cost attribution</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.6;}}
  .wrap{{max-width:860px;margin:0 auto;padding:32px 20px 64px;}}
  h1{{font-size:1.6rem;margin:0 0 2px;}}
  h2{{font-size:1.15rem;border-bottom:1px solid #334155;padding-bottom:.3em;margin:1.8em 0 .6em;color:#fff;}}
  .sub{{color:#94a3b8;font-size:.9rem;}}
  table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:.9rem;}}
  td{{padding:6px 10px;border-bottom:1px solid #334155;vertical-align:middle;}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums;color:#e2e8f0;white-space:nowrap;}}
  .barcell{{width:40%;}}
  .bar{{display:inline-block;width:calc(100% - 44px);height:12px;background:#243349;border-radius:6px;overflow:hidden;vertical-align:middle;}}
  .fill{{height:100%;background:#38bdf8;}}
  .pct{{margin-left:8px;color:#94a3b8;font-size:.8rem;}}
  .totalbox{{background:#1e293b;border:1px solid #334155;border-left:3px solid #38bdf8;border-radius:8px;padding:14px 18px;margin:14px 0;}}
  .totalbox .big{{font-size:1.4rem;font-weight:700;color:#fff;}}
  .totalbox .naive{{color:#94a3b8;font-size:.92rem;margin-top:4px;}}
  .metric{{display:flex;justify-content:space-between;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:8px 14px;margin:6px 0;font-size:.92rem;}}
  .mlbl{{color:#94a3b8;}}
  .mval{{color:#fff;font-weight:600;}}
  code{{background:#243349;padding:1px 6px;border-radius:5px;font-size:.85em;color:#cbd5e1;}}
  .recon{{color:#22c55e;font-size:.85rem;margin-top:4px;}}
</style></head><body><div class="wrap">
<h1>Claude Code cost attribution</h1>
<p class="sub">root <code>{html.escape(report.root)}</code> &middot; pricing <code>{html.escape(report.pricing_source)}</code></p>
<p class="sub">sessions parsed: {report.parsed.sessions_seen} &middot; subagent runs: {report.parsed.subagent_runs_seen}</p>

<div class="totalbox">
  <div class="big">{_money(a.total.with_cache)} <span style="color:#94a3b8;font-weight:400;font-size:.9rem;">cache-aware</span></div>
  <div class="naive">naive (no cache accounting): {_money(a.total.without_cache)} ({delta_pct:+.0f}% vs cache-aware)</div>
</div>

<h2>Cost by project</h2>
<table>{rows(a.by_project, extra_col=True)}</table>

<h2>Cost by skill</h2>
<p class="sub">Heuristic span: active from the turn after a Skill call to the next one.</p>
<table>{rows(a.by_skill)}</table>
<p class="recon">reconciles to total: {'yes' if reconciles(a.total, a.by_skill) else 'no'}</p>

<h2>Cost by subagent</h2>
<p class="sub"><code>agentType</code> from <code>.meta.json</code> - a hard signal, not a heuristic.</p>
<table>{rows(a.by_agent_type)}</table>
<p class="recon">reconciles to total: {'yes' if reconciles(a.total, a.by_agent_type) else 'no'}</p>

<h2>Burn-rate gauge</h2>
{burn_html}
{unmatched_html}
<p class="sub" style="margin-top:28px">Generated by claude-cost-attribution. Offline, no network calls, no data leaves this machine.</p>
</div></body></html>"""
