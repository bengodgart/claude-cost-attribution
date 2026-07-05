# PRD: claude-cost-attribution (ccat)

**One-liner (from brief 08):** A zero-dependency CLI that reads local `~/.claude/projects/*.jsonl` transcripts and reports cache-aware token cost attributed per project, per skill, and per subagent, plus a plan-cap burn-rate gauge, for any Claude Code Pro/Max user who gets no cost dashboard and can't answer "which of my skills is burning my weekly cap?"

**Usefulness (from brief 08):** Usage analytics are officially "not available to individual Pro or Max plans," and a consolidated feature request rolls up 10+ open issues as the single most-requested feature category across the Claude Code issue tracker. ccusage (16.5k stars) proves the demand and nails raw totals. The un-served slice is the differentiator: (a) cache-aware cost using `cache_creation_input_tokens` / `cache_read_input_tokens` with the correct multipliers, (b) per-skill / per-subagent attribution, (c) burn-rate vs a configurable weekly cap.

## v1 scope (capped), traced to the brief

| Brief requirement | Where it lives |
|---|---|
| Parse `~/.claude/projects/*.jsonl` (path overridable) into per-message usage | `ccat/parser.py::parse_root`, `discover_sessions` (auto-detects a projects root, a single project dir, or a single `.jsonl` file) |
| Cache-aware cost with the correct multipliers; show cost with and without cache accounting | `ccat/pricing.py::cost_for_event` returns both `with_cache` and `without_cache`; `pricing.json` holds the editable rates |
| Attribution by project (directory) | `ccat/attribution.py::attribute` -> `by_project`, keyed by the transcript's own `cwd` field (falls back to the directory slug, explicitly labeled, if `cwd` is ever absent) |
| Attribution by skill invocation, explicit when the signal is absent | `ccat/parser.py` skill-span heuristic (documented as a heuristic everywhere it surfaces) + `NO_SKILL` bucket in every report; never a silent "other" |
| Attribution by subagent/Task | `ccat/parser.py` reads Claude Code's own `subagents/agent-*.jsonl` + `.meta.json` files (a hard signal, not inferred) -> `MAIN_SESSION` bucket for everything outside a subagent run |
| Burn-rate gauge: rolling spend vs a configurable weekly cap, days-to-cap at current rate | `ccat/burnrate.py::compute_burn_rate`; cap is a CLI flag (`--weekly-cap`), never scraped |
| One report: top-N costliest + burn gauge, terminal + optional HTML; README opens with a real number | `ccat/report.py` (text/markdown/HTML); `README.md` opens with the fixture run's real 60%/10% numbers |
| Editable local pricing config, no network | `pricing.json` at repo root, loaded fresh every run by `ccat/pricing.py::load_pricing` |

## Non-goals (do not build - from brief 08)

A hosted dashboard, accounts, live telemetry, uploading transcripts anywhere, scraping Anthropic's plan API, multi-provider support. Re-implementing ccusage's raw totals without the attribution/cache/burn angle is explicitly called out as over-build in the brief; this tool does not compete with ccusage on totals.

## Design decisions not spelled out in the brief (and why)

- **Skill attribution is a documented heuristic, not a hard claim.** A transcript records that a `Skill` tool was called; it never records where that skill's effect ends. This tool attributes every turn from the call onward to that skill until the next `Skill` call, and labels this "heuristic span" in the CLI, Markdown, and HTML output every time the table appears - so nobody mistakes it for a certainty the data does not support.
- **Subagent attribution is a hard signal, and the report says so.** Claude Code writes a separate transcript file per spawned subagent with an `agentType` in its sidecar. This tool just reads it. The report distinguishes this explicitly from the skill heuristic above it, because they carry different confidence.
- **Every split reconciles to the same grand total, and is tested to.** `by_skill` and `by_agent_type` are each a full partition of every parsed usage event (including an explicit `(no skill)` / `(main session, no subagent)` bucket), so summing either one always equals the total - proven in `tests/test_ccat.py`, not just asserted.
- **Model pricing matches by substring, not exact ID.** Real transcripts carry snapshot-dated model IDs (`claude-opus-4-8` seen in a live install). Matching `"opus" in model_id.lower()` means a new snapshot prices correctly with zero code changes; an unmatched model falls back to a labeled default rate and is named in the report, never silently mispriced without a flag.

## Demo path (stranger sees value in under 2 minutes)

Clone -> `python -m ccat report fixtures/claude_projects/-P-demo-tutor --weekly-cap 5.00` -> see the cache-aware vs naive total, the skill split (one skill at 60%), the subagent split, and the burn gauge. Then point it at `~/.claude/projects` to audit a real setup, still at $0, still offline.

## Done when

- The CLI reads the bundled fixture transcript set and prints the attributed, cache-aware report in under 2 minutes for a fresh clone. (Verified: see EVIDENCE.md.)
- The cache-aware total matches a hand-summed spot check on the fixture transcript (pasted in EVIDENCE.md), and the per-skill split sums to the project total with no lost tokens (also pasted, and enforced by `tests/test_ccat.py::test_per_skill_split_reconciles_to_total_no_lost_tokens`).
- README opens with a real number; copy passes the no-em-dash sweep. Repo public, MIT, $0, no network calls.
