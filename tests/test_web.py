import os
import asyncio
from datetime import datetime, UTC

import pytest

# ✅ MUST set DB before importing FastAPI app
from mcp_shark.logger import set_db_path, init_db, log_message

TEST_DB_DIR = "tests/test_logs"
TEST_DB = os.path.join(TEST_DB_DIR, "test_web.db")

os.makedirs(TEST_DB_DIR, exist_ok=True)
set_db_path(TEST_DB)  # ensure all modules use the test DB
init_db()

from fastapi.testclient import TestClient
from mcp_shark.web.server import app, broadcast_new_log


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """
    Prepare a clean SQLite DB for web tests.
    Ensures logs are isolated from live sniffing logs.
    """
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    set_db_path(TEST_DB)  # reset again just in case
    init_db()

    log_message({
        "timestamp": datetime.now(UTC),
        "src_ip": "127.0.0.1",
        "dst_ip": "127.0.0.1",
        "src_port": 12345,
        "dst_port": 54321,
        "direction": "incoming",
        "message": '{"jsonrpc":"2.0","method":"ping"}'
    })
    yield


client = TestClient(app)


def test_get_logs_limit():
    """
    Ensure /logs returns valid JSON and respects the limit parameter.
    """
    response = client.get("/logs?limit=1")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "message" in data[0]
    assert "ping" in data[0]["message"]


def test_get_logs_multiple():
    """
    Ensure /logs can return multiple rows when more logs are inserted.
    """
    log_message({
        "timestamp": datetime.now(UTC),
        "src_ip": "127.0.0.1",
        "dst_ip": "127.0.0.1",
        "src_port": 23456,
        "dst_port": 65432,
        "direction": "outgoing",
        "message": '{"jsonrpc":"2.0","method":"pong"}'
    })

    response = client.get("/logs?limit=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    messages = [d["message"] for d in data]
    assert any("ping" in m for m in messages)
    assert any("pong" in m for m in messages)


def test_websocket_broadcast():
    """
    Ensure /ws broadcasts new logs to all connected WebSocket clients.
    """
    with client.websocket_connect("/ws") as ws:
        broadcast_log = {
            "timestamp": datetime.now(UTC).isoformat(),
            "src": "127.0.0.1",
            "dst": "127.0.0.1",
            "message": "test-broadcast"
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(broadcast_new_log(broadcast_log))
        loop.close()

        received = ws.receive_json()
        assert received["message"] == "test-broadcast"
        assert received["src"] == "127.0.0.1"
