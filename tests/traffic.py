"""Builders for realistic MCP traffic used across the test suite."""

import json
from typing import Any

from mcphawk.store import C2S, S2C, Recorder

MODERN = "2026-07-28"
LEGACY = "2025-06-18"

WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}},
}
SEARCH_TOOL = {
    "name": "search",
    "description": "Search the knowledge base. " * 40,
    "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    },
}


def frame(**msg: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", **msg})


def modern_meta(client: str = "claude-code") -> dict[str, Any]:
    return {
        "io.modelcontextprotocol/protocolVersion": MODERN,
        "io.modelcontextprotocol/clientInfo": {"name": client, "version": "2.1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def server_meta(name: str = "weather") -> dict[str, Any]:
    return {"io.modelcontextprotocol/serverInfo": {"name": name, "version": "1.2.0"}}


class Clock:
    def __init__(self, start: float = 1_000_000.0):
        self.t = start

    def __call__(self, step: float = 0.01) -> float:
        self.t += step
        return self.t


def legacy_session(rec: Recorder, clock: Clock | None = None, **open_kwargs: Any) -> str:
    """initialize handshake, tools/list, a good call, an error and a tool error."""
    clock = clock or Clock()
    sid = rec.open_session(capture="wrap", transport="stdio", ts=clock(), **{
        "name": "weather", "target": "python weather.py", "pid": None, **open_kwargs})
    rec.record(sid, C2S, frame(id=0, method="initialize", params={
        "protocolVersion": LEGACY, "capabilities": {},
        "clientInfo": {"name": "claude-ai", "version": "0.1.0"}}), ts=clock())
    rec.record(sid, S2C, frame(id=0, result={
        "protocolVersion": LEGACY, "capabilities": {"tools": {}},
        "serverInfo": {"name": "weather-server", "version": "1.0.0"},
        "instructions": "Use get_weather for forecasts."}), ts=clock())
    rec.record(sid, C2S, frame(method="notifications/initialized"), ts=clock())
    rec.record(sid, C2S, frame(id=1, method="tools/list"), ts=clock())
    rec.record(sid, S2C, frame(id=1, result={"tools": [WEATHER_TOOL, SEARCH_TOOL]}), ts=clock())
    rec.record(sid, C2S, frame(id=2, method="tools/call", params={
        "name": "get_weather", "arguments": {"city": "Berlin"}}), ts=clock())
    rec.record(sid, S2C, frame(id=2, result={
        "content": [{"type": "text", "text": "Sunny, 21C"}]}), ts=clock(0.25))
    rec.record(sid, C2S, frame(id=3, method="tools/call", params={
        "name": "search", "arguments": {"query": "x"}}), ts=clock())
    rec.record(sid, S2C, frame(id=3, error={"code": -32602, "message": "bad query"}),
               ts=clock())
    rec.record(sid, C2S, frame(id=4, method="tools/call", params={
        "name": "get_weather", "arguments": {"city": "Atlantis"}}), ts=clock())
    rec.record(sid, S2C, frame(id=4, result={
        "isError": True, "content": [{"type": "text", "text": "unknown city"}]}),
        ts=clock())
    return sid


def modern_session(rec: Recorder, clock: Clock | None = None, headers: bool = False,
                   **open_kwargs: Any) -> str:
    """Stateless 2026-07-28 traffic including a multi round-trip chain."""
    clock = clock or Clock()
    sid = rec.open_session(capture="proxy", transport="streamable_http", ts=clock(), **{
        "name": "weather", "target": "http://localhost:9000/mcp", **open_kwargs})

    def hdrs(method: str, name: str | None = None) -> dict[str, str] | None:
        if not headers:
            return None
        out = {"Mcp-Method": method, "Authorization": "Bearer abcdefghijklmnop"}
        if name:
            out["Mcp-Name"] = name
        return out

    rec.record(sid, C2S, frame(id=1, method="server/discover", params={
        "_meta": modern_meta()}), headers=hdrs("server/discover"), ts=clock())
    rec.record(sid, S2C, frame(id=1, result={
        "resultType": "complete", "supportedVersions": [MODERN], "capabilities": {},
        "serverInfo": {"name": "weather", "version": "1.2.0"},
        "instructions": "Weather tools.", "ttlMs": 60000, "cacheScope": "public",
        "_meta": server_meta()}), ts=clock())
    rec.record(sid, C2S, frame(id=2, method="tools/list", params={"_meta": modern_meta()}),
               headers=hdrs("tools/list"), ts=clock())
    rec.record(sid, S2C, frame(id=2, result={
        "resultType": "complete", "tools": [WEATHER_TOOL], "ttlMs": 60000,
        "cacheScope": "public", "_meta": server_meta()}), ts=clock())
    rec.record(sid, C2S, frame(id=3, method="tools/call", params={
        "name": "get_weather", "arguments": {"city": "Paris"}, "_meta": modern_meta()}),
        headers=hdrs("tools/call", "get_weather"), ts=clock())
    rec.record(sid, S2C, frame(id=3, result={
        "resultType": "input_required", "requestState": "state-1",
        "inputRequests": {"u": {"method": "elicitation/create", "params": {}}},
        "_meta": server_meta()}), ts=clock())
    rec.record(sid, C2S, frame(id=4, method="tools/call", params={
        "name": "get_weather", "arguments": {"city": "Paris"}, "requestState": "state-1",
        "inputResponses": {"u": {"action": "accept"}}, "_meta": modern_meta()}),
        headers=hdrs("tools/call", "get_weather"), ts=clock())
    rec.record(sid, S2C, frame(id=4, result={
        "resultType": "complete", "content": [{"type": "text", "text": "Rain"}],
        "_meta": server_meta()}), ts=clock(0.5))
    return sid
