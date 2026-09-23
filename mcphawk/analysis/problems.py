"""One list of everything that went wrong, most severe first."""

import hashlib
import json
from typing import Any

from mcphawk.analysis import lint as lint_mod
from mcphawk.query import Query, resolve_scope

SLOW_MS = 10_000
LOOP_REPEATS = 3

_EXCHANGE_PROBLEMS = {
    "error": (lint_mod.ERROR, "JSON-RPC error"),
    "tool_error": (lint_mod.ERROR, "Tool reported an error"),
    "hung": (lint_mod.ERROR, "No response yet"),
    "abandoned": (lint_mod.WARNING, "Never answered before the session ended"),
    "cancelled": (lint_mod.INFO, "Cancelled"),
}


def _exchange_problem(exchange: dict[str, Any], server: str) -> dict[str, Any] | None:
    what = exchange["method"] + (f" {exchange['target']}" if exchange["target"] else "")
    if exchange["status"] in _EXCHANGE_PROBLEMS:
        severity, title = _EXCHANGE_PROBLEMS[exchange["status"]]
        detail = exchange["error_message"] or ""
        if exchange["error_code"] is not None:
            detail = f"[{exchange['error_code']}] {detail}".strip()
        kind = exchange["status"]
    elif (exchange["duration_ms"] or 0) >= SLOW_MS:
        severity, title, kind = lint_mod.WARNING, "Slow call", "slow"
        detail = f"{exchange['duration_ms'] / 1000:.1f}s"
    else:
        return None
    return {
        "kind": kind, "severity": severity, "title": f"{title}: {what}", "detail": detail,
        "server": server, "session_id": exchange["session_id"],
        "exchange_id": exchange["id"], "message_id": exchange["request_msg_id"],
        "at": exchange["started_at"], "count": 1,
    }


def _loops(q: Query, exchanges: list[dict[str, Any]], server: str) -> list[dict[str, Any]]:
    """Same tool called with identical arguments several times in a row."""
    problems = []
    streak: list[dict[str, Any]] = []
    last_key = None
    for exchange in [*exchanges, None]:  # sentinel flushes the last streak
        key = None
        if exchange and exchange["method"] == "tools/call":
            request = q.get_message(exchange["request_msg_id"]) or {}
            params = (request.get("body") or {}).get("params") or {}
            payload = json.dumps(params.get("arguments"), sort_keys=True)
            key = (exchange["target"], hashlib.sha1(payload.encode()).hexdigest())
        if key is not None and key == last_key:
            streak.append(exchange)
            continue
        if len(streak) >= LOOP_REPEATS:
            first = streak[0]
            problems.append({
                "kind": "loop", "severity": lint_mod.WARNING,
                "title": f"Repeated identical call: tools/call {first['target']}",
                "detail": f"{len(streak)} times in a row with the same arguments",
                "server": server, "session_id": first["session_id"],
                "exchange_id": first["id"], "message_id": first["request_msg_id"],
                "at": first["started_at"], "count": len(streak),
            })
        streak = [exchange] if key is not None else []
        last_key = key
    return problems


def find_problems(
    q: Query,
    *,
    session_id: str | None = None,
    run_key: str | None = None,
    server: str | None = None,
    include_lint: bool = True,
    min_severity: str = lint_mod.WARNING,
    limit: int = 100,
) -> dict[str, Any]:
    sessions = resolve_scope(q, session_id=session_id, run_key=run_key, server=server)
    names = {s["id"]: s["display_name"] for s in sessions}
    threshold = lint_mod.SEVERITY_ORDER[min_severity]
    problems: list[dict[str, Any]] = []
    for session in sessions:
        exchanges = q.exchanges(session_id=session["id"], live=session["live"])
        for exchange in exchanges:
            problem = _exchange_problem(exchange, session["display_name"])
            if problem:
                problems.append(problem)
        problems.extend(_loops(q, exchanges, session["display_name"]))
    if include_lint:
        for finding in lint_mod.lint(q, list(names), min_severity=min_severity):
            problems.append({
                "kind": "lint:" + finding["rule"], "severity": finding["severity"],
                "title": finding["title"], "detail": finding["detail"],
                "server": names[finding["session_id"]], "session_id": finding["session_id"],
                "exchange_id": finding["exchange_id"], "message_id": finding["message_id"],
                "at": None, "count": finding["count"],
            })
    problems = [p for p in problems if lint_mod.SEVERITY_ORDER[p["severity"]] <= threshold]
    problems.sort(key=lambda p: (lint_mod.SEVERITY_ORDER[p["severity"]], -(p["at"] or 0)))
    summary: dict[str, int] = {}
    for problem in problems:
        summary[problem["severity"]] = summary.get(problem["severity"], 0) + 1
    return {
        "sessions_checked": len(sessions),
        "summary": summary,
        "total": len(problems),
        "problems": problems[:limit],
    }
