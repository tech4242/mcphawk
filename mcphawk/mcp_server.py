"""MCPHawk's own MCP server: lets an agent debug with the same data you see.

Results are compact summaries with deep links into the web UI; full payloads
are only returned when asked for one message at a time, and always capped.
Everything is read-only.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from mcphawk import links, runs
from mcphawk.analysis import cost, drift, problems
from mcphawk.query import Query

DEFAULT_MAX_CHARS = 6000
HARD_MAX_CHARS = 40_000

INSTRUCTIONS = """\
MCPHawk records real traffic between MCP clients and servers. Use it to see
what tools were actually called, what failed, and what each server costs in
context. A run is everything one client (e.g. Claude Code) did in one stretch
of work across all its servers. Start with list_runs or find_problems; drill
into an exchange with get_exchange. Every result links to the MCPHawk web UI - share the link
when pointing the user at something.
"""


def _dump(value: Any, max_chars: int) -> str:
    text = json.dumps(value, indent=1, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n… truncated ({len(text) - max_chars} more chars)"


def _session_row(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["id"],
        "server": session["display_name"],
        "client": session.get("client_name") or session.get("client_app"),
        "transport": session["transport"],
        "protocol": session.get("protocol_version"),
        "live": session["live"],
        "exchanges": session.get("exchange_count"),
        "errors": session.get("error_count"),
        "url": links.session_url(session["id"]),
    }


def _exchange_row(exchange: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": exchange["id"],
        "call": exchange["method"] + (f" {exchange['target']}" if exchange["target"] else ""),
        "status": exchange["status"],
        "ms": round(exchange["duration_ms"]) if exchange["duration_ms"] is not None else None,
        "result_tokens": exchange["response_tokens"],
    }
    if exchange.get("error_message"):
        row["error"] = exchange["error_message"][:200]
    return row


def build_server(db: Path | str | None = None) -> MCPServer:
    q = Query(db)
    server = MCPServer("mcphawk", instructions=INSTRUCTIONS, version="1.0.0")

    @server.tool()
    def list_runs(limit: int = 10) -> str:
        """Recent agent runs, newest first: which client, when, which servers, how many
        calls failed. Pass a run_key to find_problems, context_cost or list_sessions."""
        rows = []
        for run in runs.list_runs(q, limit=min(limit, 50)):
            rows.append({
                "run_key": run["run_key"], "client": run["client"], "live": run["live"],
                "started_at": run["started_at"], "last_seen_at": run["last_seen_at"],
                "servers": run["servers"], "calls": run["exchange_count"],
                "failed": run["error_count"], "url": links.run_url(run["run_key"]),
            })
        return _dump(rows, DEFAULT_MAX_CHARS)

    @server.tool()
    def list_sessions(server_name: str | None = None, run_key: str | None = None,
                      limit: int = 20) -> str:
        """Recent captured sessions (one per client<->server connection), newest first.
        run_key limits them to one agent run."""
        if run_key:
            sessions = runs.resolve_scope(q, run_key=run_key).sessions[:min(limit, 100)]
        else:
            sessions = q.list_sessions(server=server_name, limit=min(limit, 100))
        return _dump([_session_row(s) for s in sessions], DEFAULT_MAX_CHARS)

    @server.tool()
    def get_session(session_id: str, limit: int = 50) -> str:
        """One session: who talked to whom, and its most recent calls with status and timing."""
        session = q.get_session(session_id)
        if not session:
            return f"No session {session_id!r}."
        exchanges = session["exchanges"][-min(limit, 200):]
        report = {
            **_session_row({**session,
                            "exchange_count": len(session["exchanges"]),
                            "error_count": sum(e["status"] in ("error", "tool_error")
                                               for e in session["exchanges"])}),
            "server_version": session.get("server_version"),
            "era": session.get("era"),
            "shown": f"last {len(exchanges)} of {len(session['exchanges'])} exchanges",
            "exchanges": [_exchange_row(e) for e in exchanges],
        }
        return _dump(report, DEFAULT_MAX_CHARS)

    @server.tool()
    def get_exchange(exchange_id: int, max_chars: int = DEFAULT_MAX_CHARS) -> str:
        """Full request and response of one call (truncated to max_chars)."""
        exchange = q.get_exchange(exchange_id)
        if not exchange:
            return f"No exchange {exchange_id}."
        report = {
            **_exchange_row(exchange),
            "server": exchange["session"]["display_name"] if exchange["session"] else None,
            "session_id": exchange["session_id"],
            "url": links.exchange_url(exchange_id),
            "request": (exchange["request"] or {}).get("body"),
            "response": (exchange["response"] or {}).get("body"),
        }
        if exchange["chain"]:
            report["round_trips"] = [_exchange_row(e) for e in exchange["chain"]]
        return _dump(report, max(500, min(max_chars, HARD_MAX_CHARS)))

    @server.tool()
    def find_problems(session_id: str | None = None, run_key: str | None = None,
                      server_name: str | None = None, min_severity: str = "warning",
                      limit: int = 20) -> str:
        """Errors, tool failures, hung or slow calls, repeated identical calls and spec
        violations, most severe first. min_severity: error | warning | info."""
        if min_severity not in ("error", "warning", "info"):
            return "min_severity must be error, warning or info."
        report = problems.find_problems(
            q, session_id=session_id, run_key=run_key, server=server_name,
            min_severity=min_severity, limit=min(limit, 100))
        for problem in report["problems"]:
            problem.pop("at", None)
            if problem.get("exchange_id"):
                problem["url"] = links.exchange_url(problem["exchange_id"])
        return _dump(report, DEFAULT_MAX_CHARS)

    @server.tool()
    def context_cost(session_id: str | None = None, run_key: str | None = None,
                     server_name: str | None = None) -> str:
        """Estimated tokens each server adds to the model's context: tool definitions on
        every turn, and tool results when called. Includes concrete findings."""
        report = cost.context_cost(q, session_id=session_id, run_key=run_key,
                                   server=server_name)
        for entry in report["servers"]:
            entry.pop("session_ids", None)
            entry["definitions"] = entry["definitions"][:15]
            entry["calls"] = entry["calls"][:15]
        return _dump(report, DEFAULT_MAX_CHARS)

    @server.tool()
    def compare_sessions(before_session_id: str | None = None,
                         after_session_id: str | None = None,
                         server_name: str | None = None) -> str:
        """What changed between two sessions: tool definitions (added, removed, changed,
        token delta) and per-call behaviour. Give two session ids, or just server_name
        to compare its two most recent sessions."""
        if before_session_id and after_session_id:
            report = drift.compare_sessions(q, before_session_id, after_session_id)
        elif server_name:
            report = drift.latest_drift(q, server_name)
        else:
            return "Give before_session_id and after_session_id, or server_name."
        if "error" not in report:
            report["url"] = links.compare_url(report["before"]["id"], report["after"]["id"])
        return _dump(report, DEFAULT_MAX_CHARS)

    return server
