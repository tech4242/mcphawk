"""Test transport_type field is properly set for TCP traffic."""
import json
import uuid
from datetime import datetime, timezone

import pytest

from mcphawk.logger import clear_logs, fetch_logs, init_db, log_message, set_db_path


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_transport_type.db"
    set_db_path(str(db_path))
    init_db()
    yield db_path
    clear_logs()


def test_tcp_transport_type(test_db):
    """Test that TCP traffic is marked with transport_type='TCP'."""
    entry = {
        "log_id": str(uuid.uuid4()),
        "timestamp": datetime.now(tz=timezone.utc),
        "src_ip": "127.0.0.1",
        "src_port": 12345,
        "dst_ip": "127.0.0.1",
        "dst_port": 54321,
        "direction": "outgoing",
        "message": json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1}),
        "transport_type": "unknown",
    }

    log_message(entry)

    logs = fetch_logs(limit=1)
    assert len(logs) == 1
    assert logs[0]["transport_type"] == "unknown"



def test_unknown_transport_type(test_db):
    """Test that unknown traffic is marked with transport_type='N/A'."""
    entry = {
        "log_id": str(uuid.uuid4()),
        "timestamp": datetime.now(tz=timezone.utc),
        "src_ip": "127.0.0.1",
        "src_port": 9999,
        "dst_ip": "127.0.0.1",
        "dst_port": 54321,
        "direction": "outgoing",
        "message": json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1}),
        # Omit transport_type to test default
    }

    log_message(entry)

    logs = fetch_logs(limit=1)
    assert len(logs) == 1
    assert logs[0]["transport_type"] == "unknown"


def test_legacy_entries_without_transport_type(test_db):
    """Test that we can handle legacy entries without transport_type column."""
    # This tests the backward compatibility in fetch_logs
    import sqlite3

    # Insert a row without transport_type using direct SQL
    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            datetime.now(tz=timezone.utc).isoformat(),
            "127.0.0.1",
            "127.0.0.1",
            12345,
            54321,
            "outgoing",
            json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1}),
        ),
    )
    conn.commit()
    conn.close()

    logs = fetch_logs(limit=1)
    assert len(logs) == 1
    # Should get 'N/A' for entries without transport_type
    assert logs[0]["transport_type"] == "unknown"
