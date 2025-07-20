"""
Test suite for MCP-Shark Web API and WebSocket (Phase 1.6 Final).

Covers:
- REST API for fetching logs
- WebSocket broadcasting of new log entries
"""

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from mcp_shark.logger import log_message
from mcp_shark.web.server import app
from mcp_shark.web.broadcaster import broadcast_new_log

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """
    Ensure the database is cleared before each test.
    """
    import sqlite3
    from mcp_shark.logger import DB_FILE, init_db

    init_db()
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute("DELETE FROM logs;")
    conn.close()
    yield


def test_get_logs_limit():
    """
    Ensure /logs returns valid JSON and respects the limit parameter.
    """
    # Insert two logs for testing
    log_message(
        {
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "message": '{"jsonrpc":"2.0","method":"ping"}',
        }
    )
    log_message(
        {
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "message": '{"jsonrpc":"2.0","method":"pong"}',
        }
    )

    response = client.get("/logs?limit=1")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "message" in data[0]
    assert "jsonrpc" in data[0]["message"]


def test_get_logs_multiple():
    """
    Ensure /logs can return multiple rows when more logs are inserted.
    """
    # Insert multiple logs
    log_message(
        {
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "message": '{"jsonrpc":"2.0","method":"ping"}',
        }
    )
    log_message(
        {
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "message": '{"jsonrpc":"2.0","method":"pong"}',
        }
    )

    response = client.get("/logs?limit=2")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """
    Ensure that new log entries are broadcast to connected WebSocket clients.
    """
    # Connect to WebSocket
    with client.websocket_connect("/ws") as websocket:
        new_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "src": "127.0.0.1",
            "dst": "127.0.0.1",
            "message": '{"jsonrpc":"2.0","method":"testMethod"}',
            "method": "testMethod",
        }

        # Broadcast the new log
        await broadcast_new_log(new_log)

        # Receive the message
        data = websocket.receive_json()
        assert "message" in data
        assert "jsonrpc" in data["message"]
        assert data["method"] == "testMethod"
