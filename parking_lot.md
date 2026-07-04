# Parking lot: claude-cost-attribution

Ideas that surfaced during the v1 build. NOT in v1 scope.

- **`--watch` live burn-rate monitor** - tail the newest transcript and refresh the gauge as you work. v1 is a point-in-time report; a watcher is a different (still $0, still offline) mode.
- **Export to the trajectory-eval harness** - sit a wasteful subagent's cost next to its wasted-loop score from the eval project. Cross-project integration, not this tool's job.
- **Shareable HTML "cost card" for a single session** - a smaller, single-session variant of the existing `--html` report. Nice-to-have, not requested for v1.
- **Long-context pricing tier** - Anthropic prices some models differently above 200K tokens of context; v1 prices every call at the base tier. Edit `pricing.json` per-model if this matters to you; a tiered rate table is a v2 shape.
- **Semantic "which skill actually caused this cost" via a model call** - the current skill attribution is a deterministic span heuristic (documented in the report itself), not an LLM judgment call. Adding a model-based confirmation pass would cost tokens to save tokens; skip it.
- **Multi-provider support** - Claude Code only, on purpose. A generic "any LLM CLI" version is a different, bigger tool.

Product-creep tripwire (doctrine T11): accounts, a hosted dashboard, or uploading anyone's transcripts means it has become an app. Stop and park.
