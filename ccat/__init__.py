"""claude-cost-attribution (ccat): cache-aware cost attribution for Claude Code.

Reads local ~/.claude/projects/*.jsonl transcripts and reports token cost
per project, per skill, and per subagent, using cache-aware pricing
(cache_creation_input_tokens / cache_read_input_tokens with the correct
multipliers), plus a burn-rate gauge against a user-supplied weekly cap.

Deterministic, stdlib-only, offline. Never reads a real ~/.claude transcript
in tests; the test suite and the demo path use bundled fixtures. See README.md.
"""

__version__ = "0.1.0"
