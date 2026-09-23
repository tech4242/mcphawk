import json

import pytest
from mcp.client.client import Client

from mcphawk.mcp_server import DEFAULT_MAX_CHARS, _dump, build_server
from tests.traffic import Clock, legacy_session, modern_session


def text(result):
    return result.content[0].text


@pytest.fixture
def hawk(db, recorder, monkeypatch):
    monkeypatch.setenv("MCPHAWK_URL", "http://127.0.0.1:9999")
    clock = Clock()
    ids = {
        "legacy": legacy_session(recorder, clock, run_key="pid:7"),
        "modern": modern_session(recorder, clock, run_key="pid:7", name="weather"),
    }
    return build_server(db), ids


async def test_tools_are_few_and_documented(hawk):
    server, _ = hawk
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        assert sorted(t.name for t in tools) == [
            "compare_sessions", "context_cost", "find_problems", "get_exchange",
            "get_session", "list_sessions"]
        assert all(t.description for t in tools)


async def test_list_and_get_session(hawk):
    server, ids = hawk
    async with Client(server) as client:
        rows = json.loads(text(await client.call_tool("list_sessions", {})))
        assert {r["id"] for r in rows} == set(ids.values())
        assert rows[0]["url"].startswith("http://127.0.0.1:9999/s/")
        filtered = json.loads(text(await client.call_tool("list_sessions", {"run_key": "pid:7"})))
        assert len(filtered) == 2

        session = json.loads(text(await client.call_tool(
            "get_session", {"session_id": ids["legacy"], "limit": 2})))
        assert session["shown"] == "last 2 of 5 exchanges"
        assert session["errors"] == 2
        assert session["exchanges"][-1]["error"] == "unknown city"
        assert "No session" in text(await client.call_tool("get_session", {"session_id": "x"}))


async def test_get_exchange_with_chain_and_truncation(hawk, query):
    server, ids = hawk
    async with Client(server) as client:
        retry = [e for e in query.get_session(ids["modern"])["exchanges"]
                 if e["method"] == "tools/call"][-1]
        report = json.loads(text(await client.call_tool("get_exchange", {"exchange_id": retry["id"]})))
        assert report["response"]["result"]["content"][0]["text"] == "Rain"
        assert [r["status"] for r in report["round_trips"]] == ["input_required", "ok"]
        assert report["url"] == f"http://127.0.0.1:9999/x/{retry['id']}"
        small = text(await client.call_tool("get_exchange", {"exchange_id": retry["id"],
                                                             "max_chars": 10}))
        assert "truncated" in small
        assert "No exchange" in text(await client.call_tool("get_exchange", {"exchange_id": 999}))


async def test_find_problems_and_cost(hawk):
    server, ids = hawk
    async with Client(server) as client:
        report = json.loads(text(await client.call_tool("find_problems", {})))
        assert report["summary"]["error"] >= 2
        assert all("at" not in p for p in report["problems"])
        assert any(p.get("url", "").startswith("http://127.0.0.1:9999/x/") for p in report["problems"])
        bad = text(await client.call_tool("find_problems", {"min_severity": "bad"}))
        assert "min_severity must be" in bad

        cost = json.loads(text(await client.call_tool("context_cost", {"run_key": "pid:7"})))
        assert cost["fixed_tokens_per_turn"] > 0
        assert all("session_ids" not in s for s in cost["servers"])


async def test_compare_sessions(hawk):
    server, ids = hawk
    async with Client(server) as client:
        report = json.loads(text(await client.call_tool("compare_sessions", {
            "before_session_id": ids["legacy"], "after_session_id": ids["modern"]})))
        assert report["tools"]["removed"] == ["search"]
        assert report["url"].startswith("http://127.0.0.1:9999/compare?")
        latest = json.loads(text(await client.call_tool("compare_sessions",
                                                        {"server_name": "weather"})))
        assert latest["before"]["id"] == ids["legacy"]
        missing = json.loads(text(await client.call_tool("compare_sessions",
                                                         {"server_name": "nobody"})))
        assert "error" in missing
        assert "Give" in text(await client.call_tool("compare_sessions", {}))


def test_dump_truncates():
    assert _dump({"a": 1}, 100) == json.dumps({"a": 1}, indent=1)
    long = _dump({"a": "x" * (DEFAULT_MAX_CHARS * 2)}, DEFAULT_MAX_CHARS)
    assert long.endswith("more chars)")
