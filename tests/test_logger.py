"""Tests for the logger module."""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcphawk.logger import fetch_logs, init_db, log_message, set_db_path


class TestLogger:
    """Test the basic logger functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        # Set the temporary path
        set_db_path(temp_path)
        init_db()

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_init_db(self, temp_db):
        """Test database initialization."""
        # Database should exist
        assert Path(temp_db).exists()

        # Check schema
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Get table info
        cursor.execute("PRAGMA table_info(logs)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}

        # Check all expected columns exist
        expected_columns = {
            "log_id": "TEXT",
            "timestamp": "DATETIME",
            "src_ip": "TEXT",
            "dst_ip": "TEXT",
            "src_port": "INTEGER",
            "dst_port": "INTEGER",
            "direction": "TEXT",
            "message": "TEXT",
            "transport_type": "TEXT",
            "metadata": "TEXT",
            "pid": "INTEGER"
        }

        for col, dtype in expected_columns.items():
            assert col in columns
            assert columns[col] == dtype

        conn.close()

    def test_log_message_basic(self, temp_db):
        """Test basic message logging."""
        entry = {
            "log_id": "test-001",
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "192.168.1.1",
            "dst_ip": "192.168.1.2",
            "src_port": 3000,
            "dst_port": 3001,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            "transport_type": "streamable_http",
            "metadata": '{"test": true}'
        }

        log_message(entry)

        # Fetch and verify
        logs = fetch_logs(10)
        assert len(logs) == 1
        assert logs[0]["log_id"] == "test-001"
        assert logs[0]["src_ip"] == "192.168.1.1"
        assert logs[0]["dst_ip"] == "192.168.1.2"
        assert logs[0]["src_port"] == 3000
        assert logs[0]["dst_port"] == 3001
        assert logs[0]["transport_type"] == "streamable_http"

    def test_fetch_logs_limit(self, temp_db):
        """Test fetching logs with limit."""
        # Log multiple entries
        for i in range(5):
            entry = {
                "log_id": f"test-{i:03d}",
                "timestamp": datetime.now(tz=timezone.utc),
                "src_ip": "127.0.0.1",
                "dst_ip": "127.0.0.1",
                "src_port": 3000 + i,
                "dst_port": 4000 + i,
                "direction": "outgoing",
                "message": f'{{"jsonrpc":"2.0","method":"test{i}","id":{i}}}',
                "transport_type": "streamable_http",
                "metadata": '{}'
            }
            log_message(entry)

        # Fetch with limit
        logs = fetch_logs(3)
        assert len(logs) == 3

        # Should be in reverse chronological order (newest first)
        assert logs[0]["log_id"] == "test-004"
        assert logs[1]["log_id"] == "test-003"
        assert logs[2]["log_id"] == "test-002"


class TestPIDSupport:
    """Test PID field in database schema and operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        # Set the temporary path
        set_db_path(temp_path)
        init_db()

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_schema_includes_pid(self, temp_db):
        """Test that database schema includes PID column."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Get table info
        cursor.execute("PRAGMA table_info(logs)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}

        assert "pid" in columns
        assert columns["pid"] == "INTEGER"

        conn.close()

    def test_log_message_with_pid(self, temp_db):
        """Test logging message with PID."""
        entry = {
            "log_id": "test-123",
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "stdio",
            "dst_ip": "stdio",
            "src_port": None,
            "dst_port": None,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            "transport_type": "stdio",
            "pid": 12345,
            "metadata": '{"test": true}'
        }

        log_message(entry)

        # Fetch and verify
        logs = fetch_logs(1)
        assert len(logs) == 1
        assert logs[0]["pid"] == 12345
        assert logs[0]["src_port"] is None
        assert logs[0]["dst_port"] is None

    def test_log_message_without_pid(self, temp_db):
        """Test logging message without PID (network traffic)."""
        entry = {
            "log_id": "test-456",
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "src_port": 3000,
            "dst_port": 3001,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            "transport_type": "streamable_http",
            "metadata": '{"test": true}'
        }

        log_message(entry)

        # Fetch and verify
        logs = fetch_logs(1)
        assert len(logs) == 1
        assert logs[0]["pid"] is None
        assert logs[0]["src_port"] == 3000
        assert logs[0]["dst_port"] == 3001

    def test_mixed_traffic_types(self, temp_db):
        """Test handling both stdio (with PID) and network (with ports) traffic."""
        # Log stdio traffic
        stdio_entry = {
            "log_id": "stdio-1",
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "stdio",
            "dst_ip": "stdio",
            "src_port": None,
            "dst_port": None,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"stdio_test","id":1}',
            "transport_type": "stdio",
            "pid": 99999,
            "metadata": '{"wrapper": true}'
        }
        log_message(stdio_entry)

        # Log network traffic
        network_entry = {
            "log_id": "network-1",
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "192.168.1.1",
            "dst_ip": "192.168.1.2",
            "src_port": 8080,
            "dst_port": 8081,
            "direction": "incoming",
            "message": '{"jsonrpc":"2.0","result":"ok","id":1}',
            "transport_type": "streamable_http",
            "metadata": '{"test": true}'
        }
        log_message(network_entry)

        # Fetch all logs
        logs = fetch_logs(10)
        assert len(logs) == 2

        # Find each log by ID
        stdio_log = next(log for log in logs if log["log_id"] == "stdio-1")
        network_log = next(log for log in logs if log["log_id"] == "network-1")

        # Verify stdio log
        assert stdio_log["transport_type"] == "stdio"
        assert stdio_log["pid"] == 99999
        assert stdio_log["src_port"] is None
        assert stdio_log["dst_port"] is None

        # Verify network log
        assert network_log["transport_type"] == "streamable_http"
        assert network_log["pid"] is None
        assert network_log["src_port"] == 8080
        assert network_log["dst_port"] == 8081

    def test_query_by_pid(self, temp_db):
        """Test querying logs by PID."""
        # Log multiple entries with different PIDs
        for i in range(3):
            entry = {
                "log_id": f"test-{i}",
                "timestamp": datetime.now(tz=timezone.utc),
                "src_ip": "stdio",
                "dst_ip": "stdio",
                "direction": "outgoing",
                "message": f'{{"jsonrpc":"2.0","method":"test{i}","id":{i}}}',
                "transport_type": "stdio",
                "pid": 12345 if i < 2 else 67890,
                "metadata": '{}'
            }
            log_message(entry)

        # Direct SQL query to filter by PID
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM logs WHERE pid = ?", (12345,))
        rows = cursor.fetchall()

        assert len(rows) == 2
        for row in rows:
            assert row["pid"] == 12345

        conn.close()

    def test_backward_compatibility(self, temp_db):
        """Test that old logs without PID field still work."""
        # Directly insert an old-style log without PID
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Insert without specifying PID (should be NULL)
        cursor.execute("""
            INSERT INTO logs (log_id, timestamp, src_ip, dst_ip, src_port, dst_port,
                            direction, message, transport_type, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "old-style-1",
            datetime.now(tz=timezone.utc).isoformat(),
            "127.0.0.1",
            "127.0.0.1",
            3000,
            3001,
            "outgoing",
            '{"jsonrpc":"2.0","method":"test","id":1}',
            "streamable_http",
            '{}'
        ))
        conn.commit()
        conn.close()

        # Fetch logs should work
        logs = fetch_logs(1)
        assert len(logs) == 1
        assert logs[0]["pid"] is None  # Should be None for old logs


class TestTransportType:
    """Test transport type field functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        # Set the temporary path
        set_db_path(temp_path)
        init_db()

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_log_with_transport_types(self, temp_db):
        """Test logging messages with different transport types."""
        transport_types = ["streamable_http", "http_sse", "stdio", "unknown"]

        for i, transport in enumerate(transport_types):
            entry = {
                "log_id": f"test-{transport}",
                "timestamp": datetime.now(tz=timezone.utc),
                "src_ip": "stdio" if transport == "stdio" else "127.0.0.1",
                "dst_ip": "stdio" if transport == "stdio" else "127.0.0.1",
                "src_port": None if transport == "stdio" else 3000 + i,
                "dst_port": None if transport == "stdio" else 4000 + i,
                "direction": "outgoing",
                "message": f'{{"jsonrpc":"2.0","method":"{transport}","id":{i}}}',
                "transport_type": transport,
                "pid": 12345 if transport == "stdio" else None,
                "metadata": f'{{"transport": "{transport}"}}'
            }
            log_message(entry)

        # Fetch all logs
        logs = fetch_logs(10)
        assert len(logs) == len(transport_types)

        # Verify each transport type
        for transport in transport_types:
            log = next(lg for lg in logs if lg["log_id"] == f"test-{transport}")
            assert log["transport_type"] == transport

            if transport == "stdio":
                assert log["pid"] == 12345
                assert log["src_port"] is None
                assert log["dst_port"] is None
            else:
                assert log["pid"] is None
                assert log["src_port"] is not None
                assert log["dst_port"] is not None

