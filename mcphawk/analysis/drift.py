"""What changed between two captures: tool definitions and behaviour."""

import json
from typing import Any

from mcphawk.analysis.cost import tool_definition_tokens
from mcphawk.protocol import mcp as proto
from mcphawk.query import Query

_TOOL_FIELDS = ("title", "description", "inputSchema", "outputSchema", "annotations")


def tools_of_session(q: Query, session_id: str) -> dict[str, dict[str, Any]] | None:
    """Tools a session listed (all pages of its last listing), or None."""
    responses = q.responses_for("tools/list", [session_id])
    if not responses:
        return None
    tools: dict[str, dict[str, Any]] = {}
    for response in responses:
        for tool in proto.tools_from_list(response["body"]):
            tools[str(tool.get("name"))] = tool
    return tools


def tool_drift(old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]) -> dict[str, Any]:
    changed = []
    for name in sorted(set(old) & set(new)):
        fields = [
            f for f in _TOOL_FIELDS
            if json.dumps(old[name].get(f), sort_keys=True)
            != json.dumps(new[name].get(f), sort_keys=True)
        ]
        if fields:
            changed.append({
                "name": name, "fields": fields,
                "token_delta": tool_definition_tokens(new[name])["total"]
                - tool_definition_tokens(old[name])["total"],
            })
    old_tokens = sum(tool_definition_tokens(t)["total"] for t in old.values())
    new_tokens = sum(tool_definition_tokens(t)["total"] for t in new.values())
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": changed,
        "definition_tokens": {"before": old_tokens, "after": new_tokens,
                              "delta": new_tokens - old_tokens},
    }


def _behaviour(q: Query, session_id: str) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for exchange in q.exchanges(session_id=session_id):
        key = exchange["method"] + (f" {exchange['target']}" if exchange["target"] else "")
        entry = stats.setdefault(key, {"calls": 0, "errors": 0, "total_ms": 0.0,
                                       "result_tokens": 0})
        entry["calls"] += 1
        entry["errors"] += exchange["status"] in ("error", "tool_error")
        entry["total_ms"] += exchange["duration_ms"] or 0
        entry["result_tokens"] += exchange["response_tokens"]
    for entry in stats.values():
        entry["avg_ms"] = round(entry.pop("total_ms") / entry["calls"], 1)
    return stats


def compare_sessions(q: Query, before_id: str, after_id: str) -> dict[str, Any]:
    before = q.get_session_header(before_id)
    after = q.get_session_header(after_id)
    if not before or not after:
        missing = before_id if not before else after_id
        return {"error": f"session {missing} not found"}

    old_tools = tools_of_session(q, before_id)
    new_tools = tools_of_session(q, after_id)
    tools = (tool_drift(old_tools, new_tools)
             if old_tools is not None and new_tools is not None else None)

    old_calls, new_calls = _behaviour(q, before_id), _behaviour(q, after_id)
    calls = []
    for key in sorted(set(old_calls) | set(new_calls)):
        a, b = old_calls.get(key), new_calls.get(key)
        calls.append({"call": key, "before": a, "after": b})

    def header(session: dict[str, Any]) -> dict[str, Any]:
        return {k: session.get(k) for k in (
            "id", "display_name", "server_name", "server_version", "protocol_version",
            "started_at")}

    return {
        "before": header(before),
        "after": header(after),
        "server_version_changed": before.get("server_version") != after.get("server_version"),
        "tools": tools,
        "calls": calls,
    }


def latest_drift(q: Query, server: str) -> dict[str, Any]:
    """Compare the two most recent sessions of a server that listed tools."""
    sessions = [s for s in q.list_sessions(server=server, limit=50)
                if tools_of_session(q, s["id"]) is not None]
    if len(sessions) < 2:
        return {"error": f"need two sessions of {server!r} that listed tools"}
    return compare_sessions(q, sessions[1]["id"], sessions[0]["id"])
