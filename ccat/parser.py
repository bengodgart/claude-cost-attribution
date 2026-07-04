"""Parse a Claude Code `projects/` tree into a flat list of UsageEvents.

Expected on-disk layout (this is what `~/.claude/projects/` actually looks
like, confirmed against a real local install):

    <root>/<project-slug>/<session-uuid>.jsonl                      (main transcript)
    <root>/<project-slug>/<session-uuid>/subagents/agent-*.jsonl    (one file per subagent run)
    <root>/<project-slug>/<session-uuid>/subagents/agent-*.meta.json (agentType, description)

`root` can be that top-level `projects/` directory (many project-slugs), a
single project-slug directory (many sessions, one project), or a single
`.jsonl` file. All three are auto-detected.

Two signals this module extracts that are NOT raw totals:
- skill span: when an assistant turn calls the `Skill` tool, every
  subsequent turn (until the next Skill call) is labeled with that skill,
  until proven otherwise by another Skill call. This is a heuristic, not a
  hard signal - transcripts do not mark where a skill's effect "ends" - and
  it is labeled as such everywhere it is reported.
- subagent run: each `agent-*.jsonl` file under `subagents/` is a hard
  signal (Claude Code writes one file per spawned subagent), labeled by the
  `agentType` in its sidecar `.meta.json`.

Nothing here reads or is tested against a real ~/.claude/projects directory;
tests and the bundled demo use fixtures/ only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

NO_SKILL = "(no skill)"
MAIN_SESSION = "(main session, no subagent)"
UNKNOWN_AGENT_TYPE = "(unknown agent type - missing .meta.json)"


@dataclass
class UsageEvent:
    project: str
    session_id: str
    source_file: str
    source: str  # "main" | "subagent"
    agent_type: str  # MAIN_SESSION for main-transcript events
    skill: str  # NO_SKILL if no Skill tool call is active yet
    model: Optional[str]
    timestamp: Optional[datetime]
    input_tokens: int
    cache_creation_1h: int
    cache_creation_5m: int
    cache_read_tokens: int
    output_tokens: int


@dataclass
class SessionGroup:
    main: Path
    project_dir_name: str
    subagents: list


@dataclass
class ParseResult:
    events: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    sessions_seen: int = 0
    subagent_runs_seen: int = 0


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _project_fallback(project_dir_name: str) -> str:
    return f"(directory: {project_dir_name})"


def discover_sessions(root: Path):
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"no such path: {root}")

    if root.is_file():
        if root.suffix != ".jsonl":
            raise ValueError(f"not a .jsonl transcript: {root}")
        yield SessionGroup(main=root, project_dir_name=root.parent.name, subagents=[])
        return

    own_jsonl = sorted(root.glob("*.jsonl"))
    project_dirs = [root] if own_jsonl else sorted(p for p in root.iterdir() if p.is_dir())

    for project_dir in project_dirs:
        for jsonl_path in sorted(project_dir.glob("*.jsonl")):
            session_dir = project_dir / jsonl_path.stem
            subagents_dir = session_dir / "subagents"
            subs = sorted(subagents_dir.glob("agent-*.jsonl")) if subagents_dir.is_dir() else []
            yield SessionGroup(main=jsonl_path, project_dir_name=project_dir.name, subagents=subs)


def _iter_json_lines(path: Path, warnings: list):
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                warnings.append(f"{path}:{line_no}: skipped unparsable JSON line")
                continue


def _parse_transcript_file(
    path: Path,
    source: str,
    agent_type: str,
    project_fallback: str,
    warnings: list,
) -> list:
    events: list = []
    last_project = None
    current_skill = NO_SKILL

    for obj in _iter_json_lines(path, warnings):
        cwd = obj.get("cwd")
        if isinstance(cwd, str) and cwd:
            last_project = cwd

        if obj.get("type") != "assistant":
            continue
        message = obj.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if isinstance(usage, dict):
            cache_creation = usage.get("cache_creation") or {}
            if cache_creation:
                cache_1h = int(cache_creation.get("ephemeral_1h_input_tokens", 0) or 0)
                cache_5m = int(cache_creation.get("ephemeral_5m_input_tokens", 0) or 0)
            else:
                # older transcripts before the 1h-cache option existed: the flat
                # cache_creation_input_tokens field was always a 5-minute write.
                cache_1h = 0
                cache_5m = int(usage.get("cache_creation_input_tokens", 0) or 0)

            events.append(
                UsageEvent(
                    project=last_project or project_fallback,
                    session_id=obj.get("sessionId") or obj.get("session_id") or path.stem,
                    source_file=str(path),
                    source=source,
                    agent_type=agent_type,
                    skill=current_skill,
                    model=message.get("model"),
                    timestamp=_parse_timestamp(obj.get("timestamp")),
                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                    cache_creation_1h=cache_1h,
                    cache_creation_5m=cache_5m,
                    cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                )
            )

        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Skill"
                ):
                    skill_name = (block.get("input") or {}).get("skill")
                    if skill_name:
                        current_skill = str(skill_name)

    return events


def _load_agent_type(meta_path: Path, warnings: list) -> str:
    if not meta_path.is_file():
        warnings.append(f"{meta_path}: missing .meta.json sidecar, agent type unknown")
        return UNKNOWN_AGENT_TYPE
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (json.JSONDecodeError, OSError):
        warnings.append(f"{meta_path}: unreadable .meta.json, agent type unknown")
        return UNKNOWN_AGENT_TYPE
    agent_type = meta.get("agentType")
    if not agent_type:
        warnings.append(f"{meta_path}: .meta.json has no agentType field, agent type unknown")
        return UNKNOWN_AGENT_TYPE
    return str(agent_type)


def parse_root(root) -> ParseResult:
    result = ParseResult()
    for group in discover_sessions(Path(root)):
        result.sessions_seen += 1
        fallback = _project_fallback(group.project_dir_name)
        result.events.extend(
            _parse_transcript_file(
                group.main, "main", MAIN_SESSION, fallback, result.warnings
            )
        )
        for sub_path in group.subagents:
            result.subagent_runs_seen += 1
            meta_path = sub_path.with_name(sub_path.stem + ".meta.json")
            agent_type = _load_agent_type(meta_path, result.warnings)
            result.events.extend(
                _parse_transcript_file(
                    sub_path, "subagent", agent_type, fallback, result.warnings
                )
            )
    return result
