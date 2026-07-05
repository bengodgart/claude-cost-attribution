# claude-cost-attribution

**See which of your Claude Code skills and subagents is actually burning your weekly cap, priced the way Anthropic actually bills you.** Point it at your `~/.claude/projects` transcripts and it reports cache-aware token cost per project, per skill, and per subagent, plus a burn-rate gauge against a budget you set.

Claude Code Pro and Max plans ship no cost dashboard. Anthropic's own issue tracker rolls up 10+ open requests for exactly this under one heading: usage analytics "not available to individual Pro or Max plans." Third-party tools like [ccusage](https://github.com/ryoppippi/ccusage) (16.5k stars) prove people want this badly enough to build it themselves, and ccusage is genuinely good at raw totals. What none of them do well is the part that actually changes your behavior: **which specific skill or subagent burned the tokens**, priced **correctly for prompt caching** instead of as if every token were plain input.

```
$ python -m ccat report fixtures/claude_projects/-P-demo-tutor --weekly-cap 5.00

TOTAL cost, cache-aware:       $0.3438
TOTAL cost, naive (no cache):  $0.3785  (+10% vs cache-aware)

Cost by skill (heuristic span: active from the turn after a Skill call to the next one)
       $0.2060    60%  [#################-----------]  generate-guide
       $0.1150    33%  [#########-------------------]  (no skill)
       $0.0228     7%  [##--------------------------]  pretty-guide
  reconciles to total: yes

Cost by subagent (agentType from .meta.json - hard signal, not heuristic)
       $0.2762    80%  [######################------]  (main session, no subagent)
       $0.0625    18%  [#####-----------------------]  executor
       $0.0051     1%  [----------------------------]  general-purpose
  reconciles to total: yes
```

That is a real run against the bundled fixture session, not a cherry-picked number. One skill (`generate-guide`) accounted for 60% of this session's cost. Ignoring the cache discount entirely would have overstated the bill by 10%. Neither fact was visible from the raw transcript until something read it this way.

## Quickstart (3 commands)

```bash
git clone https://github.com/bengodgart/claude-cost-attribution
cd claude-cost-attribution
python -m ccat report fixtures/claude_projects/-P-demo-tutor --weekly-cap 5.00
```

Python 3.9+, standard library only, nothing to install. `pytest` is only needed to run the test suite, not the tool itself.

## Run it on your own transcripts

```bash
python -m ccat report "$HOME/.claude/projects" --weekly-cap 100
```

On Windows: `python -m ccat report "$env:USERPROFILE\.claude\projects" --weekly-cap 100`. Nothing is uploaded and nothing is written back into your `.claude` folder; it only reads.

## What it reports

- **Cache-aware total, with and without cache accounting, side by side.** `cache_creation_input_tokens` costs MORE than a fresh input token (you are paying to write the cache: 1.25x for a 5-minute write, 2x for a 1-hour write). `cache_read_input_tokens` costs 90% LESS (a cache hit). Reporting the naive number next to the accurate one is the whole point - it shows exactly how wrong "just count input tokens" is for your actual mix.
- **Per-skill attribution.** Whenever a transcript shows a `Skill` tool call, every turn from the next one onward is attributed to that skill, until another `Skill` call changes it. This is a **heuristic span**, not a hard signal - transcripts do not mark where a skill's effect ends - and the report labels it that way every time it appears. The bucket always includes an explicit `(no skill)` row for everything outside a span, so nothing is silently folded into a hidden "other."
- **Per-subagent attribution.** Claude Code writes one `agent-*.jsonl` file per spawned subagent, with a `.meta.json` sidecar naming its `agentType`. This IS a hard signal - Claude Code emits it, this tool just reads it - labeled `(main session, no subagent)` for everything that ran in the orchestrator itself.
- **Burn-rate gauge.** Trailing 7-day spend, a daily rate, and (if you pass `--weekly-cap`) percent-of-cap used and days-to-cap at the current rate. The cap is a number you supply; there is no API for a Pro/Max plan's usage limits, so nothing here is scraped or guessed.
- **Both splits always reconcile.** The per-skill total and the per-subagent total each sum back to the grand total exactly - checked in the test suite, not just asserted in prose.

## About the pricing

Rates live in `pricing.json` at the repo root, not in the code, so a price change is a one-line edit and never needs a new release or a network call. The cache-write and cache-read multipliers (1.25x, 2x, 0.1x) are stable across Claude models per Anthropic's published prompt-caching behavior; only the base input/output rate differs per model, matched by substring (`opus`, `sonnet`, `haiku`) so a new model snapshot ID still prices correctly without a code change. A model the config does not recognize is priced at an explicit fallback rate and flagged by name in the report - never silently guessed.

This does not yet model the higher long-context tier some models apply above 200K tokens of prompt; every call is priced at the base tier. Edit `pricing.json` if that matters for your usage.

## Credit where it's due

[ccusage](https://github.com/ryoppippi/ccusage) already solves raw session/day/model totals well, and if that is all you need, use it. This tool exists for the three things it does not do: cache-aware cost (not just raw token counts), attribution by skill and subagent (not just by session), and a burn-rate gauge against your own budget. It is not a 17th "totals" tool.

## Report-only, offline, on purpose

It never writes to your `.claude` folder, never calls the network, and never uploads a transcript anywhere. It reads, it prices, it prints. That is the entire contract.

## Tests

```bash
python -m pytest tests/ -v   # 14 tests, bundled fixtures only - never your real ~/.claude data
```

## Why I built it

I have 60+ skills and lean on subagents constantly, and I had genuinely no idea which of either was eating my plan. Anthropic's own tracker says this is the single most-requested missing feature for Claude Code, and the data to answer it was sitting on my disk the whole time, in a transcript format nobody outside Claude Code itself has a reason to parse carefully. ccusage already nails the raw-totals question. The gap was cache-aware accuracy and knowing which specific skill or subagent was responsible - so that's what I built, not a 17th totals tool.

## License

MIT. See [LICENSE](LICENSE).
