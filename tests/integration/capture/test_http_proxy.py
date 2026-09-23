import json

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from mcphawk.capture.http_proxy import Proxy
from mcphawk.capture.http_sessions import HttpSessions
from mcphawk.query import Query
from tests.traffic import modern_meta, server_meta

UPSTREAM = "http://upstream.test/mcp"
LEGACY = "http://upstream.test/sse"


async def mcp_endpoint(request: Request) -> Response:
    msg = json.loads(await request.body())
    if "id" not in msg:
        return Response(status_code=202)
    if msg["method"] == "initialize":
        return JSONResponse(
            {"jsonrpc": "2.0", "id": msg["id"], "result": {
                "protocolVersion": "2025-06-18", "serverInfo": {"name": "up", "version": "1"}}},
            headers={"Mcp-Session-Id": "sess-1"})
    if msg["method"] == "tools/call":
        async def events():
            yield b": ping\n\n"
            yield (b'data: {"jsonrpc":"2.0","method":"notifications/progress",'
                   b'"params":{"progress":1}}\n\n')
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {
                "resultType": "complete", "content": [{"type": "text", "text": "ok"}],
                "_meta": server_meta("up")}}
            yield f"data: {json.dumps(body)}\n\n".encode()
        return StreamingResponse(events(), media_type="text/event-stream")
    return JSONResponse({"jsonrpc": "2.0", "id": msg["id"], "result": {
        "resultType": "complete", "tools": [], "ttlMs": 0, "cacheScope": "public",
        "_meta": server_meta("up")}}, headers={"X-Upstream": "yes"})


async def sse_endpoint(request: Request) -> Response:
    async def events():
        yield b"event: endpoint\ndata: /messages?session_id=abc\n\n"
        yield b'data: {"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"old"}}}\n\n'
    return StreamingResponse(events(), media_type="text/event-stream")


async def get_stream(request: Request) -> Response:
    async def events():
        yield b'id: 9\ndata: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}\n\n'
    return StreamingResponse(events(), media_type="text/event-stream")


async def messages_endpoint(request: Request) -> Response:
    return Response(status_code=202)


upstream_app = Starlette(routes=[
    Route("/mcp", mcp_endpoint, methods=["POST"]),
    Route("/mcp", get_stream, methods=["GET"]),
    Route("/sse", sse_endpoint),
    Route("/messages", messages_endpoint, methods=["POST"]),
])


@pytest.fixture
async def proxy_client(recorder):
    proxy = Proxy({"modern": UPSTREAM, "legacy": LEGACY, "down": "http://down.test/mcp"},
                  recorder, transport=_Router())
    app = Starlette(routes=proxy.routes())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://proxy.test") as client:
        yield client
    await proxy.aclose()


class _Router(httpx.AsyncBaseTransport):
    """Sends upstream.test to the fake server; everything else fails to connect."""

    def __init__(self):
        self._app = httpx.ASGITransport(app=upstream_app)

    async def handle_async_request(self, request):
        if request.url.host != "upstream.test":
            raise httpx.ConnectError("connection refused", request=request)
        return await self._app.handle_async_request(request)


def rpc(id=None, method="tools/list", **params):
    msg = {"jsonrpc": "2.0", "method": method, "params": {"_meta": modern_meta(), **params}}
    if id is not None:
        msg["id"] = id
    return msg


async def test_modern_json_and_sse_responses(proxy_client, db):
    listing = await proxy_client.post("/p/modern", json=rpc(1),
                                      headers={"Mcp-Method": "tools/list"})
    assert listing.status_code == 200
    assert listing.headers["x-upstream"] == "yes"
    assert listing.json()["result"]["tools"] == []

    call = await proxy_client.post("/p/modern", json=rpc(2, "tools/call", name="t"))
    assert call.headers["content-type"].startswith("text/event-stream")
    assert call.text.count("data:") == 2
    assert ": ping" in call.text  # passthrough keeps comments

    note = await proxy_client.post("/p/modern", json=rpc(None, "notifications/x"))
    assert note.status_code == 202

    q = Query(db)
    [session] = q.list_sessions()
    assert session["capture"] == "proxy"
    assert session["name"] == "modern"
    assert session["client_name"] == "claude-code"
    assert session["server_name"] == "up"
    detail = q.get_session(session["id"])
    assert [e["status"] for e in detail["exchanges"]] == ["ok", "ok"]
    assert detail["notification_count"] == 2
    q.close()


async def test_legacy_handshake_binds_session_header(proxy_client, db):
    init = {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "clientInfo": {"name": "cursor", "version": "1"}}}
    first = await proxy_client.post("/p/modern", json=init)
    assert first.headers["mcp-session-id"] == "sess-1"
    follow = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    await proxy_client.post("/p/modern", json=follow, headers={"Mcp-Session-Id": "sess-1"})
    stream = await proxy_client.get("/p/modern", headers={"Mcp-Session-Id": "sess-1",
                                                          "Accept": "text/event-stream"})
    assert "list_changed" in stream.text

    q = Query(db)
    [session] = q.list_sessions()
    assert session["era"] == "legacy"
    assert session["exchange_count"] == 2
    assert q.get_session(session["id"])["notification_count"] == 1
    q.close()


async def test_legacy_http_sse_rewrites_endpoint(proxy_client, db):
    stream = await proxy_client.get("/p/legacy", headers={"Accept": "text/event-stream"})
    assert "data: /p/legacy/~/messages?session_id=abc" in stream.text
    posted = await proxy_client.post("/p/legacy/~/messages?session_id=abc",
                                     json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert posted.status_code == 202

    q = Query(db)
    [session] = q.list_sessions()
    assert session["transport"] == "http_sse"
    assert session["server_name"] is None  # response 1 had no matching request
    assert q.get_session(session["id"])["message_count"] == 2
    q.close()


async def test_unknown_upstream_and_unreachable(proxy_client, db):
    missing = await proxy_client.post("/p/nope", json=rpc(1))
    assert missing.status_code == 404
    down = await proxy_client.post("/p/down", json=rpc(5, "tools/call", name="x"))
    assert down.status_code == 502
    q = Query(db)
    [exchange] = q.exchanges()
    assert exchange["status"] == "error"
    assert "upstream unreachable" in exchange["error_message"]
    q.close()


async def test_sub_paths(recorder):
    proxy = Proxy(lambda: {"a": "http://h.test/base/"}, recorder)
    assert proxy._upstream_url("a", "", "") == "http://h.test/base/"
    assert proxy._upstream_url("a", "x/y", "q=1") == "http://h.test/base/x/y?q=1"
    assert proxy._upstream_url("a", "~/root", "") == "http://h.test/root"
    assert proxy._upstream_url("a", "~", "") == "http://h.test/"
    assert proxy._upstream_url("b", "", "") is None
    await proxy.aclose()


def test_serialize_endpoint_variants():
    event = type("E", (), {"event": "endpoint", "data": "http://other.test/m", "id": "3"})
    assert Proxy._serialize(event, "n", UPSTREAM) == (
        b"event: endpoint\nid: 3\ndata: http://other.test/m\n\n")
    relative = type("E", (), {"event": "endpoint", "data": "messages?s=1", "id": None})
    assert b"data: /p/n/~/messages?s=1" in Proxy._serialize(relative, "n", UPSTREAM)


def test_http_sessions_rollover_and_unknown_stream(recorder):
    clock = [1000.0]
    sessions = HttpSessions(recorder, "proxy", now=lambda: clock[0])
    a = sessions.for_request("u", {}, [rpc(1)])
    assert sessions.for_request("u", {}, [rpc(2)]) == a
    clock[0] += 31 * 60
    assert sessions.for_request("u", {}, [rpc(3)]) != a
    anon = sessions.for_request("u", None, [{"jsonrpc": "2.0", "id": 1, "method": "x"}])
    assert anon != a
    assert sessions.for_sse_stream("u", {}) is None
    assert sessions.for_sse_stream("u", {"Mcp-Session-Id": "nope"}) is None
    sessions.bind_session_header(a, "u", None)
