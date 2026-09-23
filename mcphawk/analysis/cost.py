"""Context cost: what MCP servers put into a model's context window.

Two kinds of cost matter to agent builders:

* **fixed** - tool definitions (and server instructions) that clients inject
  into the prompt on every turn, whether or not a tool is used;
* **variable** - tool results that land in the conversation when called.
"""

from collections import defaultdict
from typing import Any

from mcphawk.protocol import mcp as proto
from mcphawk.protocol.tokens import estimate_json, estimate_text
from mcphawk.query import Query
from mcphawk.runs import resolve_scope

LARGE_RESULT_TOKENS = 10_000
LARGE_DEFINITION_TOKENS = 800


def tool_definition_tokens(tool: dict[str, Any]) -> dict[str, int]:
    description = estimate_text(str(tool.get("description") or ""))
    schema = estimate_json(tool.get("inputSchema"))
    output_schema = estimate_json(tool.get("outputSchema"))
    name = estimate_text(str(tool.get("name") or ""))
    return {
        "description": description,
        "schema": schema + output_schema,
        "total": name + description + schema + output_schema,
    }


def _latest_tools(q: Query, session_ids: list[str]) -> list[dict[str, Any]]:
    """Tool set from the newest session that listed tools (pages merged)."""
    responses = q.responses_for("tools/list", session_ids)
    if not responses:
        return []
    newest = responses[-1]["session_id"]
    tools: dict[str, dict[str, Any]] = {}
    for response in responses:
        if response["session_id"] != newest:
            continue
        for tool in proto.tools_from_list(response["body"]):
            tools[str(tool.get("name"))] = tool
    return list(tools.values())


def _instructions_tokens(q: Query, session_ids: list[str]) -> int:
    for method in ("server/discover", "initialize"):
        responses = q.responses_for(method, session_ids)
        if responses:
            return estimate_text(proto.instructions_of(responses[-1]["body"]) or "")
    return 0


def context_cost(
    q: Query,
    *,
    session_id: str | None = None,
    run_key: str | None = None,
    server: str | None = None,
    top: int = 10,
) -> dict[str, Any]:
    scope = resolve_scope(q, session_id=session_id, run_key=run_key, server=server)
    by_server: dict[str, list[str]] = defaultdict(list)
    for session in scope.sessions:
        by_server[session["display_name"]].append(session["id"])

    servers = []
    heaviest: list[dict[str, Any]] = []
    for label, ids in by_server.items():
        tools = _latest_tools(q, ids)
        definitions = sorted(
            ({"name": t.get("name"), **tool_definition_tokens(t)} for t in tools),
            key=lambda d: d["total"], reverse=True)
        calls: dict[str, dict[str, Any]] = {}
        for session_id_ in ids:
            for exchange in q.exchanges(session_id=session_id_, method="tools/call",
                                        since=scope.since, until=scope.until):
                stats = calls.setdefault(exchange["target"] or "?", {
                    "tool": exchange["target"] or "?", "calls": 0, "errors": 0,
                    "result_tokens": 0, "max_result_tokens": 0})
                stats["calls"] += 1
                stats["errors"] += exchange["status"] in ("error", "tool_error")
                stats["result_tokens"] += exchange["response_tokens"]
                stats["max_result_tokens"] = max(
                    stats["max_result_tokens"], exchange["response_tokens"])
                heaviest.append({
                    "exchange_id": exchange["id"], "session_id": exchange["session_id"],
                    "server": label, "tool": exchange["target"],
                    "tokens": exchange["response_tokens"]})
        for stats in calls.values():
            stats["avg_result_tokens"] = round(stats["result_tokens"] / stats["calls"])

        called = set(calls)
        instructions = _instructions_tokens(q, ids)
        fixed = sum(d["total"] for d in definitions) + instructions
        servers.append({
            "server": label,
            "session_ids": ids,
            "fixed_tokens_per_turn": fixed,
            "instructions_tokens": instructions,
            "tool_count": len(definitions),
            "definitions": definitions,
            "unused_tools": [d["name"] for d in definitions if d["name"] not in called],
            "calls": sorted(calls.values(), key=lambda c: c["result_tokens"], reverse=True),
            "result_tokens": sum(c["result_tokens"] for c in calls.values()),
        })

    servers.sort(key=lambda s: s["fixed_tokens_per_turn"], reverse=True)
    heaviest.sort(key=lambda h: h["tokens"], reverse=True)
    return {
        "estimate": "≈4 chars/token; images counted as a flat 1500",
        "fixed_tokens_per_turn": sum(s["fixed_tokens_per_turn"] for s in servers),
        "result_tokens": sum(s["result_tokens"] for s in servers),
        "servers": servers,
        "heaviest_results": heaviest[:top],
        "findings": _findings(servers, heaviest),
    }


def _findings(servers: list[dict[str, Any]], heaviest: list[dict[str, Any]]) -> list[str]:
    findings = []
    for server in servers:
        big = [d for d in server["definitions"] if d["total"] >= LARGE_DEFINITION_TOKENS]
        for definition in big:
            findings.append(
                f"{server['server']}: tool '{definition['name']}' definition costs "
                f"≈{definition['total']} tokens every turn")
        unused = server["unused_tools"]
        if server["calls"] and unused:
            wasted = sum(d["total"] for d in server["definitions"] if d["name"] in unused)
            findings.append(
                f"{server['server']}: {len(unused)} of {server['tool_count']} tools were "
                f"never called here (≈{wasted} tokens/turn)")
    findings.extend(
        f"{h['server']}: a '{h['tool']}' result was ≈{h['tokens']} tokens "
        f"(exchange {h['exchange_id']})"
        for h in heaviest if h["tokens"] >= LARGE_RESULT_TOKENS)
    return findings
