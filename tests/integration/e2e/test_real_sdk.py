"""End to end: the official MCP SDK on both sides, MCPHawk in the middle."""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

from mcphawk.analysis import lint
from mcphawk.query import Query
from mcphawk.web.app import create_app

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sdk_server.py"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _Server(uvicorn.Server):
    def install_signal_handlers(self):  # pragma: no cover - not in main thread
        pass


def _serve(app) -> tuple[_Server, int]:
    port = _free_port()
    server = _Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:  # pragma: no cover
            raise RuntimeError("server did not start")
        time.sleep(0.02)
    return server, port


async def _exercise(client: Client) -> None:
    tools = await client.list_tools()
    assert {t.name for t in tools.tools} == {"get_weather", "explode"}
    result = await client.call_tool("get_weather", {"city": "Oslo"})
    assert result.content[0].text == "Sunny in Oslo"
    failed = await client.call_tool("explode", {})
    assert failed.is_error


@pytest.mark.parametrize(("mode", "era"), [("legacy", "legacy"), ("auto", "modern")])
async def test_stdio_through_wrap(db, mode, era):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcphawk", "wrap", "--name", "weather", "--", sys.executable, str(FIXTURE)],
        env={**os.environ, "MCPHAWK_DB": str(db)},
    )
    async with Client(params, mode=mode) as client:
        await _exercise(client)

    q = Query(db)
    [session] = q.list_sessions()
    detail = q.get_session(session["id"])
    assert detail["name"] == "weather"
    assert detail["server_name"] == "sdk-weather"
    assert detail["server_version"] == "3.1.4"
    assert detail["era"] == era
    calls = [e for e in detail["exchanges"] if e["method"] == "tools/call"]
    assert [(c["target"], c["status"]) for c in calls] == [
        ("get_weather", "ok"), ("explode", "tool_error")]
    assert calls[1]["error_message"] == "Error executing tool explode"  # what the wire says
    if era == "modern":
        errors = [f for f in lint.lint_session(q, session["id"]) if f["severity"] == "error"]
        assert errors == [], errors
    q.close()


async def test_streamable_http_through_proxy(db):
    sys.path.insert(0, str(FIXTURE.parent))
    try:
        from sdk_server import server as sdk_server
    finally:
        sys.path.pop(0)
    upstream, upstream_port = _serve(sdk_server.streamable_http_app())
    hawk, hawk_port = _serve(create_app(
        db, upstreams=lambda: {"weather": f"http://127.0.0.1:{upstream_port}/mcp"},
        with_mcp=False, static_dir=None))
    try:
        async with Client(f"http://127.0.0.1:{hawk_port}/p/weather") as client:
            await _exercise(client)
    finally:
        upstream.should_exit = hawk.should_exit = True

    q = Query(db)
    [session] = q.list_sessions()
    assert session["capture"] == "proxy"
    assert session["transport"] == "streamable_http"
    assert session["server_name"] == "sdk-weather"
    assert session["era"] == "modern"
    statuses = [e["status"] for e in q.get_session(session["id"])["exchanges"]]
    assert statuses.count("tool_error") == 1
    errors = [f for f in lint.lint_session(q, session["id"]) if f["severity"] == "error"]
    assert errors == [], errors
    q.close()
