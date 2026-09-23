import json

import pytest
from fastapi.testclient import TestClient

from mcphawk.web.app import create_app
from tests.traffic import Clock, legacy_session, modern_session


@pytest.fixture
def client(db, recorder):
    clock = Clock()
    legacy_session(recorder, clock, client_key="pid:1", client_app="claude")
    modern_session(recorder, clock, client_key="pid:1", client_app="claude", name="search")
    app = create_app(db, upstreams=lambda: {"demo": "http://127.0.0.1:1/mcp"}, with_mcp=False,
                     static_dir=None)
    with TestClient(app, base_url="http://127.0.0.1:8484") as c:
        yield c


GUARD = {"X-MCPHawk": "1"}


def test_read_api(client):
    stats = client.get("/api/stats").json()
    assert stats["sessions"] == 2
    assert stats["proxies"] == {"demo": "http://127.0.0.1:1/mcp"}

    [run] = client.get("/api/runs").json()
    assert run["run_key"].startswith("pid:1@")
    assert run["client"] == "Claude Code"
    detail = client.get(f"/api/runs/{run['run_key']}").json()
    assert len(detail["sessions"]) == 2
    assert client.get("/api/runs/nope").status_code == 404

    sessions = client.get("/api/sessions", params={"server": "search"}).json()
    sid = sessions[0]["id"]
    assert client.get(f"/api/sessions/{sid}").json()["era"] == "modern"
    assert client.get("/api/sessions/zzz").status_code == 404
    assert len(client.get(f"/api/sessions/{sid}/messages").json()) == 8
    assert client.get(f"/api/sessions/{sid}/lint").json() != []
    assert client.get("/api/sessions/zzz/lint").status_code == 404

    calls = client.get("/api/exchanges", params={"method": "tools/call", "q": "Berlin"}).json()
    assert len(calls) == 1
    exchange = client.get(f"/api/exchanges/{calls[0]['id']}").json()
    assert exchange["request"]["body"]["params"]["arguments"] == {"city": "Berlin"}
    assert client.get("/api/exchanges/999").status_code == 404
    assert client.get(f"/api/messages/{exchange['request_msg_id']}").status_code == 200
    assert client.get("/api/messages/999").status_code == 404


def test_analysis_api(client):
    problems = client.get("/api/problems").json()
    assert problems["summary"]["error"] >= 2
    assert client.get("/api/problems", params={"min_severity": "loud"}).status_code == 422
    run_key = client.get("/api/runs").json()[0]["run_key"]
    assert len(client.get("/api/sessions", params={"run_key": run_key}).json()) == 2
    cost = client.get("/api/cost", params={"run_key": run_key}).json()
    assert {s["server"] for s in cost["servers"]} == {"weather", "search"}
    sessions = [s["id"] for s in client.get("/api/sessions").json()]
    compare = client.get("/api/compare", params={"before": sessions[1], "after": sessions[0]})
    assert compare.json()["tools"]["removed"] == ["search"]
    missing = client.get("/api/compare", params={"before": "x", "after": sessions[0]})
    assert missing.status_code == 404


def test_setup_and_clear(client, monkeypatch):
    from mcphawk.install import installer

    monkeypatch.setattr(installer, "plan", lambda **kw: [])
    assert client.get("/api/setup").json() == {"servers": []}
    assert client.delete("/api/data", headers=GUARD).status_code == 400
    cleared = client.delete("/api/data", params={"confirm": True}, headers=GUARD)
    assert cleared.json() == {"cleared": True}
    assert client.get("/api/stats").json()["sessions"] == 0


def test_live_websocket_pushes_new_messages(client, recorder):
    from mcphawk.store import C2S
    from mcphawk.web import app as web_app

    web_app.LIVE_POLL_S = 0.05
    with client.websocket_connect("/api/live") as ws:
        sid = recorder.open_session(capture="wrap", transport="stdio")
        recorder.record(sid, C2S, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}))
        update = ws.receive_json()
        assert update["type"] == "messages"
        assert update["items"][0]["method"] == "ping"


def test_proxy_route_is_mounted(client):
    missing = client.post("/p/unknown", json={"jsonrpc": "2.0", "id": 1, "method": "x"})
    assert missing.status_code == 404
    down = client.post("/p/demo", json={"jsonrpc": "2.0", "id": 1, "method": "x"})
    assert down.status_code == 502


def test_no_ui_fallback(client):
    assert "not built" in client.get("/").json()["message"]


def test_spa_serving(db, tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>app</html>")
    (static / "assets" / "app.js").write_text("js")
    (static / "favicon.svg").write_text("<svg/>")
    app = create_app(db, upstreams=dict, with_mcp=False, static_dir=static)
    with TestClient(app) as c:
        assert c.get("/").text == "<html>app</html>"
        assert c.get("/s/abc123").text == "<html>app</html>"  # client-side route
        assert c.get("/assets/app.js").text == "js"
        assert c.get("/favicon.svg").text == "<svg/>"
        assert c.get("/../../etc/passwd").text == "<html>app</html>"
        assert c.get("/api/unknown").status_code == 404


def test_mcp_endpoint_is_mounted(db):
    app = create_app(db, upstreams=dict, static_dir=None)
    with TestClient(app, base_url="http://127.0.0.1:8484") as c:
        response = c.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {"name": "t", "version": "1"},
                "io.modelcontextprotocol/clientCapabilities": {}}}},
            headers={"Accept": "application/json, text/event-stream",
                     "Mcp-Method": "tools/list", "MCP-Protocol-Version": "2026-07-28"})
        assert response.status_code == 200
        assert "find_problems" in response.text


def test_mutations_require_guard_header_and_local_host(client):
    assert client.delete("/api/data", params={"confirm": True}).status_code == 403
    rebound = client.delete("/api/data", params={"confirm": True},
                            headers={**GUARD, "Host": "evil.example:8484"})
    assert rebound.status_code == 403
    ipv6 = client.delete("/api/data", headers={**GUARD, "Host": "[::1]"})
    assert ipv6.status_code == 400  # passed the guard, failed on confirm
    assert client.get("/api/stats").status_code == 200  # reads are not guarded


def test_replay_endpoint_errors(client):
    missing = client.post("/api/exchanges/999/replay", json={}, headers=GUARD)
    assert missing.status_code == 409
    assert "not found" in missing.json()["detail"]
