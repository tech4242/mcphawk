"""Agent runs: everything one client did in one stretch of work.

A run groups the sessions of one client across all its MCP servers, and ends
when the client goes quiet. Grouping happens at read time:

1. **By client.** stdio sessions share the client process that launched them
   (``client_key`` ``pid:...``). HTTP sessions have no process, so they are
   grouped by the client's self-reported name and folded into a process group
   of the same client that was active at the same time.
2. **By time.** A gap of ``RUN_GAP_S`` without any call starts a new run, so a
   Claude Code window left open all day becomes several runs, one per task.

A run key is ``<client>@<start>``; the start of a run never moves once later
traffic arrives, so links stay valid.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from mcphawk.query import Query

RUN_GAP_S = 300.0

# Process names and self-reported client names -> what people call the client.
_CLIENT_LABELS = {
    "claude": "Claude Code",
    "claude-code": "Claude Code",
    "Claude": "Claude Desktop",
    "claude-ai": "Claude Desktop",
    "Cursor": "Cursor",
    "cursor-vscode": "Cursor",
    "Code": "VS Code",
    "Code Helper": "VS Code",
    "Visual Studio Code": "VS Code",
    "Windsurf": "Windsurf",
}


def client_label(sessions: list[dict[str, Any]], group: str) -> str:
    """What people call the client: a known process name beats a self-reported one."""
    if group.startswith("replay:"):
        return "Replay"
    names = [s.get(key) for key in ("client_app", "client_name") for s in sessions]
    names = [n for n in names if n]
    known = next((_CLIENT_LABELS[n] for n in names if n in _CLIENT_LABELS), None)
    return known or next(iter(names), "Unknown client")


def _group_of(session: dict[str, Any]) -> str:
    if session.get("client_key"):
        return session["client_key"]
    if session.get("client_name"):
        return f"client:{session['client_name']}"
    return f"session:{session['id']}"


@dataclass
class Run:
    group: str
    start: float
    end: float
    session_ids: set[str] = field(default_factory=set)
    exchanges: int = 0
    errors: int = 0
    tokens: int = 0

    @property
    def key(self) -> str:
        return f"{self.group}@{int(self.start)}"


def _groups(sessions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        groups[_group_of(session)].append(session)
    # Fold HTTP sessions of a named client into an overlapping process group.
    for group in [g for g in groups if g.startswith("client:")]:
        name = group.removeprefix("client:")
        start = min(s["started_at"] for s in groups[group])
        end = max(s["last_seen_at"] for s in groups[group])
        hosts = [
            g for g, members in groups.items()
            if g.startswith("pid:") and any(m.get("client_name") == name for m in members)
            and min(m["started_at"] for m in members) <= end + RUN_GAP_S
            and max(m["last_seen_at"] for m in members) >= start - RUN_GAP_S
        ]
        if hosts:
            host = max(hosts, key=lambda g: max(m["last_seen_at"] for m in groups[g]))
            groups[host].extend(groups.pop(group))
    return groups


def _split(group: str, members: list[dict[str, Any]],
           timings: list[dict[str, Any]]) -> list[Run]:
    """Cut one client's activity into runs at idle gaps."""
    events = [(s["started_at"], s["started_at"], s["id"], None) for s in members]
    events += [(t["started_at"], t["ended_at"], t["session_id"], t) for t in timings]
    events.sort(key=lambda e: e[0])
    runs: list[Run] = []
    for start, end, session_id, timing in events:
        if not runs or start - runs[-1].end > RUN_GAP_S:
            runs.append(Run(group, start, end))
        run = runs[-1]
        run.end = max(run.end, end)
        run.session_ids.add(session_id)
        if timing:
            run.exchanges += 1
            run.errors += timing["status"] in ("error", "tool_error")
            run.tokens += timing["tokens"] or 0
    return runs


def compute_runs(q: Query) -> list[tuple[Run, list[dict[str, Any]]]]:
    """All runs with their sessions, newest first."""
    sessions, timings = q.activity()
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for timing in timings:
        by_session[timing["session_id"]].append(timing)
    result = []
    for group, members in _groups(sessions).items():
        member_timings = [t for m in members for t in by_session[m["id"]]]
        index = {m["id"]: m for m in members}
        for run in _split(group, members, member_timings):
            result.append((run, [index[sid] for sid in run.session_ids]))
    result.sort(key=lambda pair: pair[0].end, reverse=True)
    return result


def _summary(run: Run, sessions: list[dict[str, Any]], latest: bool,
             now: float) -> dict[str, Any]:
    live = latest and any(s["live"] for s in sessions) and now - run.end < RUN_GAP_S
    return {
        "run_key": run.key,
        "client": client_label(sessions, run.group),
        "started_at": run.start,
        "last_seen_at": run.end,
        "live": live,
        "servers": sorted({s["display_name"] for s in sessions}),
        "session_count": len(sessions),
        "exchange_count": run.exchanges,
        "error_count": run.errors,
        "tokens": run.tokens,
    }


def list_runs(q: Query, limit: int = 50, now: float | None = None) -> list[dict[str, Any]]:
    now = now if now is not None else time.time()
    runs = compute_runs(q)
    latest_per_group: dict[str, str] = {}
    for run, _ in runs:
        latest_per_group.setdefault(run.group, run.key)
    return [_summary(run, sessions, latest_per_group[run.group] == run.key, now)
            for run, sessions in runs[:limit]]


def find_run(q: Query, run_key: str) -> tuple[Run, list[dict[str, Any]], bool] | None:
    runs = compute_runs(q)
    latest_per_group: dict[str, str] = {}
    for run, _ in runs:
        latest_per_group.setdefault(run.group, run.key)
    for run, sessions in runs:
        if run.key == run_key:
            return run, sessions, latest_per_group[run.group] == run_key
    return None


def get_run(q: Query, run_key: str, now: float | None = None) -> dict[str, Any] | None:
    found = find_run(q, run_key)
    if not found:
        return None
    run, sessions, latest = found
    sessions = sorted(sessions, key=lambda s: s["started_at"])
    timeline = q.exchanges(session_ids=[s["id"] for s in sessions],
                           since=run.start - 1, until=run.end + 1, limit=5000)
    summary = _summary(run, sessions, latest, now if now is not None else time.time())
    return {**summary, "sessions": sessions, "timeline": timeline}


@dataclass
class Scope:
    """What an analysis should look at: sessions, optionally within a time window."""

    sessions: list[dict[str, Any]]
    since: float | None = None
    until: float | None = None


def resolve_scope(q: Query, *, session_id: str | None = None, run_key: str | None = None,
                  server: str | None = None, limit: int = 200) -> Scope:
    if session_id:
        session = q.get_session_header(session_id)
        return Scope([session] if session else [])
    if run_key:
        found = find_run(q, run_key)
        if not found:
            return Scope([])
        run, sessions, _ = found
        return Scope(sessions, run.start - 1, run.end + 1)
    return Scope(q.list_sessions(server=server, limit=limit))
