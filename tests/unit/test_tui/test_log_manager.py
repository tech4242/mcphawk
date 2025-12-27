"""Unit tests for LogManager and related classes."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from mcphawk.tui.data.log_manager import LogEntry, LogManager, LogStats


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_log_entry_creation(self):
        """Test creating a log entry."""
        entry = LogEntry(
            id=1,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            src_ip="127.0.0.1",
            src_port=3000,
            dst_ip="127.0.0.1",
            dst_port=54321,
            direction="incoming",
            message='{"jsonrpc":"2.0","method":"test","id":1}',
            transport_type="streamable_http",
            metadata={"server_name": "test-server"},
            pid=None,
        )

        assert entry.id == 1
        assert entry.src_ip == "127.0.0.1"
        assert entry.transport_type == "streamable_http"

    def test_message_type_request(self):
        """Test message_type property for request."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_type == "request"

    def test_message_type_response(self):
        """Test message_type property for response."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="incoming",
            message='{"jsonrpc":"2.0","result":{"status":"ok"},"id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_type == "response"

    def test_message_type_notification(self):
        """Test message_type property for notification."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"initialized"}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_type == "notification"

    def test_message_type_error(self):
        """Test message_type property for error."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="incoming",
            message='{"jsonrpc":"2.0","error":{"code":-32600},"id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_type == "error"

    def test_method_property(self):
        """Test method property extraction."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"tools/list","id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.method == "tools/list"

    def test_method_property_from_response(self):
        """Test method property returns None for response."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="incoming",
            message='{"jsonrpc":"2.0","result":{},"id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.method is None

    def test_method_property_invalid_json(self):
        """Test method property with invalid JSON."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message="not valid json",
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.method is None

    def test_message_id_property(self):
        """Test message_id property extraction."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":42}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_id == "42"

    def test_message_id_property_string_id(self):
        """Test message_id property with string ID."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":"abc-123"}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_id == "abc-123"

    def test_message_id_property_notification(self):
        """Test message_id property returns None for notification."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"initialized"}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_id is None

    def test_message_id_property_invalid_json(self):
        """Test message_id property with invalid JSON."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message="not valid json",
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.message_id is None

    def test_server_name_property(self):
        """Test server_name property extraction."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":1}',
            transport_type="stdio",
            metadata={"server_name": "my-mcp-server"},
            pid=12345,
        )

        assert entry.server_name == "my-mcp-server"

    def test_server_name_property_missing(self):
        """Test server_name property when not in metadata."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )

        assert entry.server_name is None


class TestLogStats:
    """Tests for LogStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = LogStats()

        assert stats.total == 0
        assert stats.requests == 0
        assert stats.responses == 0
        assert stats.notifications == 0
        assert stats.errors == 0

    def test_custom_values(self):
        """Test stats with custom values."""
        stats = LogStats(
            total=100,
            requests=50,
            responses=40,
            notifications=8,
            errors=2,
        )

        assert stats.total == 100
        assert stats.requests == 50
        assert stats.responses == 40
        assert stats.notifications == 8
        assert stats.errors == 2


class TestLogManager:
    """Tests for LogManager class."""

    def test_init_default(self):
        """Test default initialization."""
        manager = LogManager()

        assert manager.max_entries == 1000
        assert manager.entries == []
        assert manager.last_id == 0
        assert manager.stats.total == 0
        assert manager.type_filter is None
        assert manager.transport_filter is None
        assert manager.server_filter is None
        assert manager.search_query == ""

    def test_init_custom_max_entries(self):
        """Test initialization with custom max_entries."""
        manager = LogManager(max_entries=500)

        assert manager.max_entries == 500

    def test_add_entry_updates_stats(self):
        """Test that adding entries updates stats correctly."""
        manager = LogManager()

        # Add a request
        entry1 = LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"test","id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )
        manager._add_entry(entry1)

        assert manager.stats.total == 1
        assert manager.stats.requests == 1

        # Add a response
        entry2 = LogEntry(
            id=2,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="incoming",
            message='{"jsonrpc":"2.0","result":{},"id":1}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )
        manager._add_entry(entry2)

        assert manager.stats.total == 2
        assert manager.stats.responses == 1

        # Add a notification
        entry3 = LogEntry(
            id=3,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"initialized"}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )
        manager._add_entry(entry3)

        assert manager.stats.total == 3
        assert manager.stats.notifications == 1

        # Add an error
        entry4 = LogEntry(
            id=4,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="incoming",
            message='{"jsonrpc":"2.0","error":{"code":-32600},"id":2}',
            transport_type="stdio",
            metadata={},
            pid=12345,
        )
        manager._add_entry(entry4)

        assert manager.stats.total == 4
        assert manager.stats.errors == 1

    def test_add_entry_trims_when_over_max(self):
        """Test that entries are trimmed when over max."""
        manager = LogManager(max_entries=3)

        for i in range(5):
            entry = LogEntry(
                id=i + 1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message=f'{{"jsonrpc":"2.0","method":"test","id":{i + 1}}}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
            manager._add_entry(entry)

        # Should only have last 3 entries
        assert len(manager.entries) == 3
        assert manager.entries[0].id == 3
        assert manager.entries[1].id == 4
        assert manager.entries[2].id == 5

    def test_get_filtered_entries_no_filter(self):
        """Test getting entries with no filters."""
        manager = LogManager()

        for i in range(3):
            entry = LogEntry(
                id=i + 1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message=f'{{"jsonrpc":"2.0","method":"test","id":{i + 1}}}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
            manager._add_entry(entry)

        filtered = manager.get_filtered_entries()
        assert len(filtered) == 3

    def test_get_filtered_entries_type_filter(self):
        """Test filtering by message type."""
        manager = LogManager()

        # Add request
        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        # Add response
        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="incoming",
                message='{"jsonrpc":"2.0","result":{},"id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager.type_filter = "request"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1
        assert filtered[0].message_type == "request"

    def test_get_filtered_entries_transport_filter(self):
        """Test filtering by transport type."""
        manager = LogManager()

        # Add stdio entry
        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        # Add HTTP entry
        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip="127.0.0.1",
                src_port=3000,
                dst_ip="127.0.0.1",
                dst_port=54321,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":2}',
                transport_type="streamable_http",
                metadata={},
                pid=None,
            )
        )

        manager.transport_filter = "stdio"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1
        assert filtered[0].transport_type == "stdio"

    def test_get_filtered_entries_server_filter(self):
        """Test filtering by server name."""
        manager = LogManager()

        # Add entry with server name
        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={"server_name": "server-a"},
                pid=12345,
            )
        )

        # Add entry with different server
        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":2}',
                transport_type="stdio",
                metadata={"server_name": "server-b"},
                pid=12345,
            )
        )

        manager.server_filter = "server-a"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1
        assert filtered[0].server_name == "server-a"

    def test_get_filtered_entries_search_query(self):
        """Test filtering by search query."""
        manager = LogManager()

        # Add entry with specific method
        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"tools/list","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        # Add entry with different method
        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"initialize","id":2}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager.search_query = "tools"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1
        assert "tools" in filtered[0].message

    def test_get_filtered_entries_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        manager = LogManager()

        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"Tools/List","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager.search_query = "TOOLS"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1

    def test_get_filtered_entries_search_in_method(self):
        """Test that search works on method property."""
        manager = LogManager()

        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"special_method","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager.search_query = "special"
        filtered = manager.get_filtered_entries()

        assert len(filtered) == 1

    def test_get_unique_servers(self):
        """Test getting unique server names."""
        manager = LogManager()

        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={"server_name": "server-b"},
                pid=12345,
            )
        )

        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":2}',
                transport_type="stdio",
                metadata={"server_name": "server-a"},
                pid=12345,
            )
        )

        manager._add_entry(
            LogEntry(
                id=3,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":3}',
                transport_type="stdio",
                metadata={"server_name": "server-b"},  # duplicate
                pid=12345,
            )
        )

        servers = manager.get_unique_servers()

        assert servers == ["server-a", "server-b"]

    def test_get_unique_transports(self):
        """Test getting unique transport types."""
        manager = LogManager()

        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager._add_entry(
            LogEntry(
                id=2,
                timestamp=datetime.now(),
                src_ip="127.0.0.1",
                src_port=3000,
                dst_ip="127.0.0.1",
                dst_port=54321,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":2}',
                transport_type="streamable_http",
                metadata={},
                pid=None,
            )
        )

        transports = manager.get_unique_transports()

        assert transports == ["stdio", "streamable_http"]

    def test_clear(self):
        """Test clearing all entries."""
        manager = LogManager()

        manager._add_entry(
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                src_ip=None,
                src_port=None,
                dst_ip=None,
                dst_port=None,
                direction="outgoing",
                message='{"jsonrpc":"2.0","method":"test","id":1}',
                transport_type="stdio",
                metadata={},
                pid=12345,
            )
        )

        manager.last_id = 100
        manager.clear()

        assert len(manager.entries) == 0
        assert manager.last_id == 0
        assert manager.stats.total == 0

    def test_row_to_entry(self):
        """Test converting database row to LogEntry."""
        manager = LogManager()

        # Create a mock row that behaves like sqlite3.Row
        mock_row = {
            "log_id": 1,
            "timestamp": "2025-01-01T12:00:00",
            "src_ip": "127.0.0.1",
            "src_port": 3000,
            "dst_ip": "127.0.0.1",
            "dst_port": 54321,
            "direction": "incoming",
            "message": '{"jsonrpc":"2.0","result":{},"id":1}',
            "transport_type": "streamable_http",
            "metadata": '{"server_name":"test"}',
            "pid": None,
        }

        entry = manager._row_to_entry(mock_row)

        assert entry.id == 1
        assert entry.src_ip == "127.0.0.1"
        assert entry.src_port == 3000
        assert entry.direction == "incoming"
        assert entry.transport_type == "streamable_http"
        assert entry.metadata == {"server_name": "test"}

    def test_row_to_entry_invalid_metadata(self):
        """Test converting row with invalid metadata JSON."""
        manager = LogManager()

        mock_row = {
            "log_id": 1,
            "timestamp": "2025-01-01T12:00:00",
            "src_ip": None,
            "src_port": None,
            "dst_ip": None,
            "dst_port": None,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            "transport_type": "stdio",
            "metadata": "not valid json",
            "pid": 12345,
        }

        entry = manager._row_to_entry(mock_row)

        assert entry.metadata == {}

    def test_row_to_entry_null_transport(self):
        """Test converting row with null transport type."""
        manager = LogManager()

        mock_row = {
            "log_id": 1,
            "timestamp": "2025-01-01T12:00:00",
            "src_ip": None,
            "src_port": None,
            "dst_ip": None,
            "dst_port": None,
            "direction": "outgoing",
            "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            "transport_type": None,
            "metadata": None,
            "pid": 12345,
        }

        entry = manager._row_to_entry(mock_row)

        assert entry.transport_type == "unknown"

    @patch("mcphawk.tui.data.log_manager.get_db_connection")
    def test_poll_for_updates(self, mock_get_db):
        """Test polling for new entries from database."""
        manager = LogManager()

        # Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        # Setup mock rows
        mock_cursor.fetchall.return_value = [
            {
                "log_id": 1,
                "timestamp": "2025-01-01T12:00:00",
                "src_ip": None,
                "src_port": None,
                "dst_ip": None,
                "dst_port": None,
                "direction": "outgoing",
                "message": '{"jsonrpc":"2.0","method":"test","id":1}',
                "transport_type": "stdio",
                "metadata": None,
                "pid": 12345,
            },
            {
                "log_id": 2,
                "timestamp": "2025-01-01T12:00:01",
                "src_ip": None,
                "src_port": None,
                "dst_ip": None,
                "dst_port": None,
                "direction": "incoming",
                "message": '{"jsonrpc":"2.0","result":{},"id":1}',
                "transport_type": "stdio",
                "metadata": None,
                "pid": 12345,
            },
        ]

        new_entries = manager.poll_for_updates()

        assert len(new_entries) == 2
        assert manager.last_id == 2
        assert len(manager.entries) == 2
        assert manager.stats.total == 2
        assert manager.stats.requests == 1
        assert manager.stats.responses == 1

    @patch("mcphawk.tui.data.log_manager.get_db_connection")
    def test_poll_for_updates_empty(self, mock_get_db):
        """Test polling when no new entries."""
        manager = LogManager()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchall.return_value = []

        new_entries = manager.poll_for_updates()

        assert len(new_entries) == 0
        assert manager.last_id == 0
