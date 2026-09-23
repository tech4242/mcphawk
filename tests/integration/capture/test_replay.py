import json
import shlex
import sys
from pathlib import Path

import httpx
import pytest

from mcphawk import replay as rp
from mcphawk.protocol.masking import MASK
from mcphawk.store import C2S, S2C
from tests.integration.capture.test_http_proxy import upstream_app
from tests.traffic import frame, modern_meta

ECHO = str(Path(__file__).resolve().parents[2] / "fixtures" / "echo_server.py")


def stdio_session(recorder, command=None, init=True):
    target = shlex.join(command or [sys.executable, ECHO])
    sid = recorder.open_session(capture="wrap", transport="stdio", name="echo", target=target)
    if init:
        recorder.record(sid, C2S, frame(id=0, method="initialize", params={
            "protocolVersion": "2025-06-18", "clientInfo": {"name": "c", "version": "1"}}))
        recorder.record(sid, S2C, frame(id=0, result={"serverInfo": {"name": "echo"}}))
    recorder.record(sid, C2S, frame(id=1, method="tools/call", params={
        "name": "echo", "arguments": {"text": "hi"}}))
    recorder.record(sid, S2C, frame(id=1, result={"content": []}))
    return sid


def call_exchange(query, sid):
    return next(e for e in query.get_session(sid)["exchanges"] if e["method"] == "tools/call")


async def test_replay_stdio_with_edited_params(recorder, query):
    sid = stdio_session(recorder)
    original = call_exchange(query, sid)
    result = await rp.replay(query, recorder, original["id"], {"name": "echo", "arguments": {
        "text": "edited"}})
    assert result["status"] == "ok"
    assert result["response"]["result"]["echo"]["arguments"] == {"text": "edited"}
    replayed = query.get_session(result["session_id"])
    assert replayed["capture"] == "replay"
    assert replayed["client_key"] == f"replay:{original['id']}"
    assert replayed["display_name"] == "echo (replay)"
    assert replayed["ended_at"] is not None
    assert [e["method"] for e in replayed["exchanges"]] == ["initialize", "tools/call"]


async def test_replay_stdio_synthesizes_initialize(recorder, query):
    sid = stdio_session(recorder, init=False)
    result = await rp.replay(query, recorder, call_exchange(query, sid)["id"])
    assert result["status"] == "ok"
    init = query.get_session(result["session_id"])["exchanges"][0]
    request = query.get_message(init["request_msg_id"])["body"]
    assert request["params"]["clientInfo"]["name"] == "mcphawk-replay"


async def test_replay_refusals(recorder, query):
    sid = stdio_session(recorder)
    server_initiated = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(server_initiated, S2C, frame(id="s", method="roots/list"))
    masked = recorder.open_session(capture="wrap", transport="stdio", target="x")
    recorder.record(masked, C2S, frame(id=1, method="tools/call", params={"token": "abc"}))
    sse = recorder.open_session(capture="sniff", transport="http_sse", target="http://x")
    recorder.record(sse, C2S, frame(id=1, method="tools/list"))
    empty = recorder.open_session(capture="wrap", transport="stdio", target="")
    recorder.record(empty, C2S, frame(id=1, method="tools/list"))
    secret_cmd = recorder.open_session(capture="wrap", transport="stdio",
                                       target=f"server --key {MASK}")
    recorder.record(secret_cmd, C2S, frame(id=1, method="tools/list"))

    def first(session_id):
        return query.get_session(session_id)["exchanges"][0]["id"]

    cases = {
        9999: "not found",
        first(server_initiated): "only client requests",
        first(masked): "masked secrets; edit",
        first(sse): "not supported for http_sse",
        first(empty): "no command",
        first(secret_cmd): "--no-mask",
    }
    for exchange_id, message in cases.items():
        with pytest.raises(rp.ReplayError, match=message):
            await rp.replay(query, recorder, exchange_id)
    assert call_exchange(query, sid)


async def test_replay_stdio_server_dies_or_times_out(recorder, query):
    dead = stdio_session(recorder, command=[sys.executable, "-c", "print('bye')"])
    with pytest.raises(rp.ReplayError, match="exited before answering"):
        await rp.replay(query, recorder, call_exchange(query, dead)["id"])
    silent = stdio_session(recorder, command=[sys.executable, "-c",
                                              "import time; time.sleep(5)"])
    with pytest.raises(rp.ReplayError, match="no response within"):
        await rp.replay(query, recorder, call_exchange(query, silent)["id"], timeout=0.3)


class Upstream(httpx.AsyncBaseTransport):
    def __init__(self):
        self.app = httpx.ASGITransport(app=upstream_app)
        self.requests = []

    async def handle_async_request(self, request):
        self.requests.append(request)
        return await self.app.handle_async_request(request)


async def test_replay_http_modern_and_legacy(recorder, monkeypatch):
    transport = Upstream()
    original = rp._replay_http

    async def with_transport(*args):
        return await original(*args, transport=transport)

    monkeypatch.setattr(rp, "_replay_http", with_transport)
    from mcphawk.query import Query

    q = Query()
    modern = recorder.open_session(capture="proxy", transport="streamable_http",
                                   target="http://upstream.test/mcp")
    recorder.record(modern, C2S, frame(id=1, method="tools/call", params={
        "name": "t", "_meta": modern_meta()}))
    recorder.record(modern, S2C, frame(id=1, result={"resultType": "complete"}))
    exchange = q.get_session(modern)["exchanges"][0]
    result = await rp.replay(q, recorder, exchange["id"])
    assert result["response"]["result"]["content"][0]["text"] == "ok"
    sent = transport.requests[-1]
    assert sent.headers["mcp-method"] == "tools/call"
    assert sent.headers["mcp-name"] == "t"

    legacy = recorder.open_session(capture="sniff", transport="streamable_http",
                                   target="http://upstream.test/mcp")
    recorder.record(legacy, C2S, frame(id=1, method="tools/list"))
    recorder.record(legacy, S2C, frame(id=1, result={"tools": []}))
    transport.requests.clear()
    result = await rp.replay(q, recorder, q.get_session(legacy)["exchanges"][0]["id"])
    assert [json.loads(r.content)["method"] for r in transport.requests] == [
        "initialize", "notifications/initialized", "tools/list"]
    assert transport.requests[-1].headers["mcp-session-id"] == "sess-1"
    assert result["response"]["result"]["tools"] == []
    q.close()


async def test_replay_http_error_paths():
    async def handler(request):
        body = json.loads(request.content)
        if body.get("method") == "fail":
            return httpx.Response(500, text="boom")
        if body.get("method") == "silent-sse":
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  content=b"data: \n\ndata: nope\n\n")
        return httpx.Response(202)

    transport = httpx.MockTransport(handler)
    session = {"target": "http://x/mcp"}
    record = lambda *a: None  # noqa: E731
    with pytest.raises(rp.ReplayError, match="HTTP 500"):
        await rp._replay_http(session, [], {"jsonrpc": "2.0", "id": "r", "method": "fail"},
                              record, transport=transport)
    with pytest.raises(rp.ReplayError, match="did not answer"):
        await rp._replay_http(session, [], {"jsonrpc": "2.0", "id": "r", "method": "x"},
                              record, transport=transport)
    with pytest.raises(rp.ReplayError, match="did not answer"):
        await rp._replay_http(session, [], {"jsonrpc": "2.0", "id": "r",
                                            "method": "silent-sse"}, record,
                              transport=transport)
