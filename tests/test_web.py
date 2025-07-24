"""
Test suite for MCPHawk Web API and WebSocket (Phase 1.6 Final).

Covers:
- REST API for fetching logs
- WebSocket broadcasting of new log entries
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from mcphawk.logger import init_db, log_message, set_db_path
from mcphawk.web.broadcaster import broadcast_new_log
from mcphawk.web.server import app

client = TestClient(app)

# Use a temporary test database
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_web_mcphawk.db")


@pytest.fixture(autouse=True, scope="module")
def setup_test_db():
    """Set up test database for all tests in this module."""
    set_db_path(TEST_DB_PATH)
    init_db()
    yield
    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(autouse=True)
def clean_db():
    """
    Ensure the database is cleared before each test.
    """
    import sqlite3

    conn = sqlite3.connect(TEST_DB_PATH)
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

        # Receive the message (the test WebSocket doesn't send pings)
        data = websocket.receive_json()
        assert "message" in data
        assert "jsonrpc" in data["message"]
        assert data["method"] == "testMethod"


def test_empty_database_returns_empty_list():
    """Test that /logs returns empty list when database is empty."""
    response = client.get("/logs?limit=10")
    assert response.status_code == 200
    assert response.json() == []


def test_logs_persist_across_requests():
    """Test that logs persist between different API requests."""
    # Add a log
    log_message({
        "timestamp": datetime.now(timezone.utc),
        "src_ip": "192.168.1.1",
        "dst_ip": "192.168.1.2",
        "src_port": 12345,
        "dst_port": 8080,
        "direction": "incoming",
        "message": '{"jsonrpc":"2.0","method":"persistTest","id":1}'
    })

    # First request
    response1 = client.get("/logs?limit=10")
    assert response1.status_code == 200
    data1 = response1.json()
    assert len(data1) == 1
    assert "persistTest" in data1[0]["message"]

    # Second request should return the same data
    response2 = client.get("/logs?limit=10")
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2) == 1
    assert data1[0]["message"] == data2[0]["message"]


def test_logs_order_newest_first():
    """Test that logs are returned in reverse chronological order."""
    import time

    # Add logs with small delays to ensure different timestamps
    for i in range(3):
        log_message({
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "src_port": 12345,
            "dst_port": 8080,
            "direction": "incoming",
            "message": f'{{"jsonrpc":"2.0","method":"order{i}","id":{i}}}'
        })
        time.sleep(0.01)  # Small delay to ensure different timestamps

    response = client.get("/logs?limit=10")
    assert response.status_code == 200
    data = response.json()

    # Should be in reverse order (newest first)
    assert len(data) == 3
    assert "order2" in data[0]["message"]
    assert "order1" in data[1]["message"]
    assert "order0" in data[2]["message"]


def test_logs_default_limit():
    """Test that default limit of 50 is applied."""
    # Add 60 logs
    for i in range(60):
        log_message({
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "src_port": 12345,
            "dst_port": 8080,
            "direction": "incoming",
            "message": f'{{"jsonrpc":"2.0","method":"bulk","id":{i}}}'
        })

    # Request without limit should return 50
    response = client.get("/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 50


def test_log_fields_preserved_in_api():
    """Test that all log fields are preserved through the API."""
    test_entry = {
        "timestamp": datetime.now(timezone.utc),
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 54321,
        "dst_port": 9999,
        "direction": "outgoing",
        "message": '{"jsonrpc":"2.0","method":"fieldTest","id":"abc"}'
    }

    log_message(test_entry)

    response = client.get("/logs?limit=1")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    log = data[0]

    assert log["src_ip"] == "10.0.0.1"
    assert log["dst_ip"] == "10.0.0.2"
    assert log["src_port"] == 54321
    assert log["dst_port"] == 9999
    assert log["direction"] == "outgoing"
    assert log["message"] == '{"jsonrpc":"2.0","method":"fieldTest","id":"abc"}'
    assert "timestamp" in log  # Should be ISO format string
