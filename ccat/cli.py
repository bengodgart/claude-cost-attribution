"""Command-line interface for claude-cost-attribution.

Usage:
    python -m ccat report <path-to-projects-dir> [options]

<path> can be:
  - your real transcript root, e.g. ~/.claude/projects (Windows: %USERPROFILE%\\.claude\\projects)
  - a single project-slug directory under it
  - a single .jsonl transcript file
  - the bundled fixtures/claude_projects (for the demo / test path)

Options:
    --top N            how many rows per table (default 10)
    --weekly-cap USD    your self-declared weekly budget, for the burn-rate gauge (no cap = gauge omitted)
    --pricing PATH      override the pricing config (default: pricing.json at the repo root)
    --html PATH         also write a self-contained HTML report
    --md PATH           also write a Markdown report
    --quiet             suppress the text report on stdout

Exit code 0 on success, 2 on a usage/IO error. Offline: no network calls,
nothing is uploaded, nothing is written back to your ~/.claude tree.
"""

from __future__ import annotations

import argparse
import os
import sys

from .attribution import attribute
from .burnrate import compute_burn_rate
from .parser import parse_root
from .pricing import load_pricing
from .report import Report, render_html, render_markdown, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccat",
        description="Cache-aware Claude Code cost attribution, by project/skill/subagent (offline).",
    )
    sub = parser.add_subparsers(dest="command")
    r = sub.add_parser("report", help="report cost attribution for a transcript root")
    r.add_argument("target", help="path to ~/.claude/projects, a project dir, or a .jsonl file")
    r.add_argument("--top", type=int, default=10, help="rows per table (default 10)")
    r.add_argument("--weekly-cap", type=float, default=None, help="weekly budget in USD for the burn-rate gauge")
    r.add_argument("--pricing", default=None, help="path to a pricing config JSON (default: repo-root pricing.json)")
    r.add_argument("--html", default=None, help="write an HTML report to this path")
    r.add_argument("--md", default=None, help="write a Markdown report to this path")
    r.add_argument("--quiet", action="store_true", help="suppress stdout text report")
    return parser


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def run(args) -> int:
    try:
        parsed = parse_root(args.target)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    pricing = load_pricing(args.pricing)
    attribution = attribute(parsed.events, pricing)
    burn = compute_burn_rate(attribution.priced_events, args.weekly_cap)

    report = Report(
        root=args.target,
        parsed=parsed,
        attribution=attribution,
        burn=burn,
        pricing_source=pricing.source,
        top_n=args.top,
    )

    if not args.quiet:
        print(render_text(report))
    if args.html:
        _ensure_parent(args.html)
        with open(args.html, "w", encoding="utf-8") as handle:
            handle.write(render_html(report))
        if not args.quiet:
            print(f"\nwrote HTML report: {args.html}")
    if args.md:
        _ensure_parent(args.md)
        with open(args.md, "w", encoding="utf-8") as handle:
            handle.write(render_markdown(report))
        if not args.quiet:
            print(f"wrote Markdown report: {args.md}")
    return 0


def main(argv: list = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "report":
        return run(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
