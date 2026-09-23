import json

from mcphawk.analysis import cost, drift, lint, problems
from mcphawk.store import C2S, S2C
from tests.traffic import (
    SEARCH_TOOL,
    WEATHER_TOOL,
    Clock,
    frame,
    legacy_session,
    modern_meta,
    modern_session,
    server_meta,
)


def test_context_cost_per_server(recorder, query):
    sid = legacy_session(recorder)
    report = cost.context_cost(query, session_id=sid)
    server = report["servers"][0]
    assert server["server"] == "weather"
    assert server["tool_count"] == 2
    assert server["definitions"][0]["name"] == "search"  # the verbose one
    assert server["instructions_tokens"] > 0
    assert server["fixed_tokens_per_turn"] == report["fixed_tokens_per_turn"]
    tools = {c["tool"]: c for c in server["calls"]}
    assert tools["get_weather"]["calls"] == 2
    assert tools["get_weather"]["errors"] == 1
    assert tools["search"]["errors"] == 1
    assert server["unused_tools"] == []
    assert report["heaviest_results"][0]["exchange_id"]


def test_context_cost_findings(recorder, query):
    sid = recorder.open_session(capture="wrap", transport="stdio", name="big")
    huge = {**SEARCH_TOOL, "description": "x" * 4000}
    recorder.record(sid, C2S, frame(id=1, method="tools/list"))
    recorder.record(sid, S2C, frame(id=1, result={"tools": [huge, WEATHER_TOOL]}))
    recorder.record(sid, C2S, frame(id=2, method="tools/call", params={"name": "search"}))
    recorder.record(sid, S2C, frame(id=2, result={
        "content": [{"type": "text", "text": "y" * 50_000}]}))
    findings = cost.context_cost(query)["findings"]
    assert any("definition costs" in f for f in findings)
    assert any("never called" in f for f in findings)
    assert any("result was" in f for f in findings)


def test_context_cost_prefers_discover_instructions_and_newest_listing(recorder, query):
    clock = Clock()
    modern_session(recorder, clock)
    newer = modern_session(recorder, clock)
    recorder.record(newer, C2S, frame(id=10, method="tools/list", params={
        "cursor": "p2", "_meta": modern_meta()}))
    recorder.record(newer, S2C, frame(id=10, result={
        "resultType": "complete", "tools": [SEARCH_TOOL], "ttlMs": 1, "cacheScope": "public",
        "_meta": server_meta()}))
    server = cost.context_cost(query)["servers"][0]
    assert server["tool_count"] == 2
    assert server["instructions_tokens"] == 4  # "Weather tools."


def test_empty_cost_report(query):
    report = cost.context_cost(query)
    assert report["servers"] == []
    assert report["fixed_tokens_per_turn"] == 0


def test_lint_clean_modern_session(recorder, query):
    sid = modern_session(recorder, headers=True)
    assert lint.lint_session(query, sid) == []


def test_lint_modern_violations(recorder, query):
    sid = recorder.open_session(capture="proxy", transport="streamable_http")
    meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}
    recorder.record(sid, C2S, frame(id=1, method="tools/list", params={"_meta": meta}),
                    headers={"Mcp-Method": "tools/call"})
    recorder.record(sid, S2C, frame(id=1, result={"tools": [WEATHER_TOOL]}))
    recorder.record(sid, C2S, frame(id=2, method="tools/call", params={
        "name": "get_weather", "_meta": meta}), headers={"Mcp-Method": "tools/call"})
    recorder.record(sid, S2C, frame(id=2, result={"resultType": "complete", "content": []}))
    recorder.record(sid, C2S, frame(id=3, method="resources/read", params={
        "uri": "file:///x", "_meta": meta}),
        headers={"Mcp-Method": "resources/read", "Mcp-Name": "file:///y"})
    recorder.record(sid, S2C, frame(id=3, error={"code": -32002, "message": "not found"}))
    recorder.record(sid, C2S, frame(id=4, method="ping", params={"_meta": meta}))
    recorder.record(sid, C2S, frame(method="notifications/roots/list_changed"))
    recorder.record(sid, S2C, frame(id="s", method="elicitation/create", params={}))
    recorder.record(sid, S2C, frame(id="t", method="custom/thing", params={}))

    rules = {f["rule"] for f in lint.lint_session(query, sid)}
    assert {
        "missing-result-type", "missing-cache-hints", "missing-server-info",
        "missing-client-info", "header-mismatch", "missing-mcp-headers",
        "legacy-not-found-code", "removed-method", "server-initiated-request",
        "deprecated-feature",
    } <= rules
    ordered = lint.lint_session(query, sid)
    assert ordered[0]["severity"] == "error"
    assert ordered[-1]["severity"] == "info"


def test_lint_legacy_and_generic_rules(recorder, query):
    sid = recorder.open_session(capture="sniff", transport="http_sse")
    recorder.record(sid, S2C, "debug: starting")
    recorder.record(sid, S2C, '{"hello": "world"}')
    recorder.record(sid, S2C, frame(id=5, result={}))
    for i, tools in enumerate([[WEATHER_TOOL, SEARCH_TOOL], [SEARCH_TOOL, WEATHER_TOOL]]):
        recorder.record(sid, C2S, frame(id=10 + i, method="tools/list"))
        recorder.record(sid, S2C, frame(id=10 + i, result={"tools": tools}))
    recorder.record(sid, S2C, frame(id=20, method="sampling/createMessage", params={}))
    findings = lint.lint_session(query, sid)
    rules = {f["rule"] for f in findings}
    assert rules == {"non-json-output", "invalid-jsonrpc", "unmatched-response",
                     "nondeterministic-tools", "deprecated-transport", "deprecated-feature"}
    non_json = next(f for f in findings if f["rule"] == "non-json-output")
    assert non_json["detail"] == "Stray output on the stream"
    assert lint.lint_session(query, "missing") == []


def test_lint_folds_repeats_and_filters_severity(recorder, query):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    for _ in range(3):
        recorder.record(sid, S2C, "log line")
    findings = lint.lint(query, [sid], min_severity="error")
    assert len(findings) == 1
    assert findings[0]["count"] == 3
    assert findings[0]["detail"] == "Stray output on stdout"


def test_find_problems(recorder, query, db):
    sid = legacy_session(recorder, clock=Clock(start=1000.0))
    recorder.record(sid, C2S, frame(id=50, method="tools/call", params={"name": "slow"}),
                    ts=2000.0)
    recorder.record(sid, S2C, frame(id=50, result={"content": []}), ts=2012.0)
    recorder.record(sid, C2S, frame(id=51, method="tools/call", params={"name": "gone"}),
                    ts=2013.0)
    recorder.record(sid, C2S, frame(id=52, method="tools/call", params={"name": "c"}),
                    ts=2014.0)
    recorder.record(sid, C2S, frame(method="notifications/cancelled",
                                    params={"requestId": 52}), ts=2015.0)
    for i in range(4):
        recorder.record(sid, C2S, frame(id=60 + i, method="tools/call", params={
            "name": "search", "arguments": {"query": "same"}}), ts=2020.0 + i)
        recorder.record(sid, S2C, frame(id=60 + i, result={"content": []}), ts=2020.5 + i)
    recorder.record(sid, S2C, "oops")
    recorder.end_session(sid, ts=2100.0)

    report = problems.find_problems(query, session_id=sid, min_severity="info")
    kinds = [p["kind"] for p in report["problems"]]
    assert {"error", "tool_error", "slow", "abandoned", "cancelled", "loop",
            "lint:non-json-output"} <= set(kinds)
    loop = next(p for p in report["problems"] if p["kind"] == "loop")
    assert loop["count"] == 4
    assert report["summary"]["error"] >= 3
    assert report["problems"][0]["severity"] == "error"

    default = problems.find_problems(query, session_id=sid)
    assert "cancelled" not in [p["kind"] for p in default["problems"]]
    no_lint = problems.find_problems(query, include_lint=False, limit=1)
    assert no_lint["total"] > 1
    assert len(no_lint["problems"]) == 1


def test_tool_drift_and_compare_sessions(recorder, query):
    clock = Clock()
    before = legacy_session(recorder, clock)
    after = recorder.open_session(capture="wrap", transport="stdio", name="weather", ts=clock())
    changed = {**WEATHER_TOOL, "description": "Get weather. Now with forecasts!"}
    new_tool = {"name": "forecast", "inputSchema": {"type": "object"}}
    recorder.record(after, C2S, frame(id=1, method="tools/list"), ts=clock())
    recorder.record(after, S2C, frame(id=1, result={"tools": [changed, new_tool]}), ts=clock())
    recorder.record(after, C2S, frame(id=2, method="tools/call", params={"name": "forecast"}),
                    ts=clock())
    recorder.record(after, S2C, frame(id=2, result={"content": []}), ts=clock())

    report = drift.compare_sessions(query, before, after)
    assert report["tools"]["added"] == ["forecast"]
    assert report["tools"]["removed"] == ["search"]
    assert report["tools"]["changed"][0]["name"] == "get_weather"
    assert report["tools"]["changed"][0]["fields"] == ["description"]
    assert report["tools"]["definition_tokens"]["delta"] < 0
    calls = {c["call"]: c for c in report["calls"]}
    assert calls["tools/call forecast"]["before"] is None
    assert calls["tools/call get_weather"]["before"]["calls"] == 2
    assert report["server_version_changed"] is True

    assert drift.latest_drift(query, "weather")["tools"]["added"] == ["forecast"]
    assert "error" in drift.latest_drift(query, "nobody")
    assert "error" in drift.compare_sessions(query, before, "missing")
    empty = recorder.open_session(capture="wrap", transport="stdio")
    assert drift.compare_sessions(query, before, empty)["tools"] is None


def test_tools_of_session_merges_pages(recorder, query):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    for i, tool in enumerate([WEATHER_TOOL, SEARCH_TOOL]):
        recorder.record(sid, C2S, frame(id=i, method="tools/list"))
        recorder.record(sid, S2C, frame(id=i, result={"tools": [tool]}))
    assert set(drift.tools_of_session(query, sid)) == {"get_weather", "search"}
    assert json.dumps(drift.tool_drift({}, {}))
