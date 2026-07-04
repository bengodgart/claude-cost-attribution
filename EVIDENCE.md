# Evidence — claude-cost-attribution ship gate

All commands run from `C:\dev\claude-cost-attribution`. Python 3.14.4, pytest 9.1.1, stdlib only for the tool itself. All runs are against the bundled `fixtures/` transcripts, never a real `~/.claude/projects` directory.

## 1. pytest suite (full output + exit code)

```
$ python -m pytest tests/ -v

============================= test session starts =============================
platform win32 -- Python 3.14.4, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Asus PC\AppData\Local\Programs\Python\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\claude-cost-attribution
configfile: pyproject.toml
collecting ... collected 14 items

tests/test_ccat.py::test_cache_aware_cost_hand_check_opus_cache_write PASSED [  7%]
tests/test_ccat.py::test_naive_cost_hand_check_sonnet_cache_read PASSED  [ 14%]
tests/test_ccat.py::test_unmatched_model_falls_back_to_default_rate_not_an_error PASSED [ 21%]
tests/test_ccat.py::test_parse_root_finds_session_and_subagents PASSED   [ 28%]
tests/test_ccat.py::test_missing_meta_json_is_flagged_not_silently_dropped PASSED [ 35%]
tests/test_ccat.py::test_cache_aware_total_matches_manual_sum_of_all_events PASSED [ 42%]
tests/test_ccat.py::test_main_session_and_subagent_sums_match_hand_check PASSED [ 50%]
tests/test_ccat.py::test_per_skill_split_reconciles_to_total_no_lost_tokens PASSED [ 57%]
tests/test_ccat.py::test_per_subagent_split_reconciles_to_total_no_lost_tokens PASSED [ 64%]
tests/test_ccat.py::test_per_project_split_reconciles_across_multiple_projects PASSED [ 71%]
tests/test_ccat.py::test_burn_rate_window_includes_all_fixture_events PASSED [ 78%]
tests/test_ccat.py::test_burn_rate_without_a_cap_omits_projection PASSED [ 85%]
tests/test_ccat.py::test_burn_rate_flags_cap_already_exceeded PASSED     [ 92%]
tests/test_ccat.py::test_burn_rate_with_no_timestamps_does_not_crash PASSED [100%]

============================= 14 passed in 0.06s ==============================
```

**Exit code: 0.** 14 passed, 0 failed, 0 skipped.

## 2. CLI against the bundled fixtures (full output + exit code)

```
$ python -m ccat report fixtures/claude_projects/-P-demo-tutor --weekly-cap 5.00

Claude Code cost attribution
root: fixtures/claude_projects/-P-demo-tutor
pricing: pricing.json (repo root)
sessions parsed: 1   subagent runs: 2

TOTAL cost, cache-aware:       $0.8528
TOTAL cost, naive (no cache):  $0.8823  (+3% vs cache-aware)
  input 30,000  cache-write-1h 14,000  cache-write-5m 2,000  cache-read 30,000  output 4,100

Cost by project
       $0.8528   100%  [############################]  C:\Users\demo\dev\demo-tutor-app  (8 turns)

Cost by skill (heuristic span: active from the turn after a Skill call to the next one)
       $0.5910    69%  [###################---------]  generate-guide
       $0.2390    28%  [########--------------------]  (no skill)
       $0.0228     3%  [#---------------------------]  pretty-guide
  reconciles to total: yes

Cost by subagent (agentType from .meta.json - hard signal, not heuristic)
       $0.6612    78%  [######################------]  (main session, no subagent)
       $0.1875    22%  [######----------------------]  executor
       $0.0041     0%  [----------------------------]  general-purpose
  reconciles to total: yes

Burn-rate gauge
  trailing 7-day window: 2026-05-30 14:05:00+00:00 to 2026-06-06 14:05:00+00:00
  spend in window: $0.8528
  daily rate: $0.1636/day (over 5.21 elapsed days)
  weekly cap: $5.0000 (user-supplied)  -  17% of cap used
  at the current daily rate: cap reached in 30.6 days
```

**Exit code: 0.** Committed copies of this same run: `examples/sample-report.md`, `examples/sample-report.html`.

## 3. Hand-check A — cache-aware total on one fixture transcript

Transcript: `fixtures/claude_projects/-P-demo-tutor/session-aaaa1111.jsonl` (the main transcript only, its 6 assistant/usage lines, excluding the two subagent files). Rates from `pricing.json`: opus $15/$75 per MTok, sonnet $3/$15 per MTok, cache-write-1h x2.0, cache-write-5m x1.25, cache-read x0.1.

Formula: `with_cache = (input*in_rate + cache_1h*in_rate*2.0 + cache_5m*in_rate*1.25 + cache_read*in_rate*0.1 + output*out_rate) / 1,000,000`

| Line | Model | input | cache_1h | cache_5m | cache_read | output | with_cache |
|---|---|---|---|---|---|---|---|
| E1 | sonnet | 10,000 | 0 | 0 | 0 | 500 | (10000*3 + 500*15)/1e6 = **0.0375** |
| E2 | sonnet | 2,000 | 0 | 0 | 8,000 | 100 | (2000*3 + 8000*3*0.1 + 100*15)/1e6 = **0.0099** |
| E3 | opus | 5,000 | 10,000 | 0 | 0 | 1,000 | (5000*15 + 10000*15*2.0 + 1000*75)/1e6 = **0.4500** |
| E4 | opus | 3,000 | 0 | 0 | 15,000 | 800 | (3000*15 + 15000*15*0.1 + 800*75)/1e6 = **0.1275** |
| E5 | sonnet | 1,000 | 0 | 2,000 | 0 | 200 | (1000*3 + 2000*3*1.25 + 200*15)/1e6 = **0.0135** |
| E6 | sonnet | 4,000 | 0 | 0 | 6,000 | 600 | (4000*3 + 6000*3*0.1 + 600*15)/1e6 = **0.0228** |

Manual sum: `0.0375 + 0.0099 + 0.4500 + 0.1275 + 0.0135 + 0.0228 = 0.6612`

Cross-check against the tool's own output: the "Cost by subagent" table above reports `(main session, no subagent) = $0.6612` — the exact main-transcript-only total, matching the hand sum to the last cent. Also asserted in `tests/test_ccat.py::test_main_session_and_subagent_sums_match_hand_check`.

## 4. Hand-check B — per-skill split sums to the project total (no lost tokens)

From the same CLI run above, scoped to the single project `-P-demo-tutor`:

```
TOTAL cost, cache-aware: $0.8528

generate-guide  $0.5910
(no skill)      $0.2390
pretty-guide    $0.0228
-----------------------
sum             $0.8528
```

`0.5910 + 0.2390 + 0.0228 = 0.8528`, exactly the project total printed on the same run. Nothing is missing and nothing double-counted: the `(no skill)` row exists explicitly rather than folding those turns into either named skill. Enforced by `tests/test_ccat.py::test_per_skill_split_reconciles_to_total_no_lost_tokens`, which checks this equality directly with `attribution.reconciles()` rather than eyeballing rounded printed numbers.

The per-subagent split reconciles the same way (`$0.6612 + $0.1875 + $0.0041 = $0.8528`), covered by `test_per_subagent_split_reconciles_to_total_no_lost_tokens`.

## Honest gaps (named, not hidden)

- Skill attribution is a heuristic span (documented in the CLI/MD/HTML output itself): a transcript records that a `Skill` tool was called, not where its effect ends. Subagent attribution, by contrast, is a hard signal read directly from Claude Code's own per-agent transcript files.
- Pricing does not yet model the higher long-context tier some models apply above 200K tokens of prompt context; every call is priced at the base tier. Noted in the README.
- This was verified against synthetic bundled fixtures only, per the brief's requirement never to read Ben's real `~/.claude` data in tests. The "run it on your own transcripts" path in the README was exercised manually against the real schema (confirmed the on-disk layout: `<project>/<session>.jsonl` + `<session>/subagents/agent-*.jsonl` + `.meta.json`) during development, but no real transcript content or numbers from that machine appear anywhere in this repo.
