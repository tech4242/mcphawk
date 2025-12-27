"""Unit tests for TUI screens."""

from datetime import datetime

from mcphawk.tui.data.log_manager import LogEntry
from mcphawk.tui.screens.detail import MessageDetailScreen


class TestMessageDetailScreen:
    """Tests for MessageDetailScreen."""

    def create_entry(
        self,
        method: str | None = "test",
        message_type: str = "request",
        transport: str = "stdio",
        server_name: str | None = None,
        src_ip: str | None = None,
        dst_ip: str | None = None,
        pid: int | None = 12345,
    ) -> LogEntry:
        """Helper to create log entries for testing."""
        if message_type == "request":
            message = f'{{"jsonrpc":"2.0","method":"{method}","id":1}}'
        elif message_type == "response":
            message = '{"jsonrpc":"2.0","result":{},"id":1}'
        elif message_type == "notification":
            message = f'{{"jsonrpc":"2.0","method":"{method}"}}'
        else:
            message = '{"jsonrpc":"2.0","error":{"code":-32600},"id":1}'

        metadata = {}
        if server_name:
            metadata["server_name"] = server_name

        return LogEntry(
            id=1,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            src_ip=src_ip,
            src_port=3000 if src_ip else None,
            dst_ip=dst_ip,
            dst_port=54321 if dst_ip else None,
            direction="outgoing",
            message=message,
            transport_type=transport,
            metadata=metadata,
            pid=pid if not src_ip else None,
        )

    def test_get_header_basic(self):
        """Test header generation with basic entry."""
        entry = self.create_entry()
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "Message Details" in header
        assert "2025-01-01 12:00:00" in header
        assert "request" in header
        assert "stdio" in header

    def test_get_header_with_method(self):
        """Test header includes method."""
        entry = self.create_entry(method="tools/list")
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "Method: tools/list" in header

    def test_get_header_with_server_name(self):
        """Test header includes server name."""
        entry = self.create_entry(server_name="my-mcp-server")
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "Server: my-mcp-server" in header

    def test_get_header_with_network_flow(self):
        """Test header shows network flow for HTTP transport."""
        entry = self.create_entry(
            src_ip="127.0.0.1",
            dst_ip="127.0.0.1",
            transport="streamable_http",
            pid=None,
        )
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "Flow:" in header
        assert "127.0.0.1:3000" in header
        assert "127.0.0.1:54321" in header

    def test_get_header_with_pid(self):
        """Test header shows PID for stdio transport."""
        entry = self.create_entry(pid=98765)
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "PID: 98765" in header

    def test_get_header_response(self):
        """Test header for response message."""
        entry = self.create_entry(message_type="response")
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        assert "Type: response" in header

    def test_get_header_no_method(self):
        """Test header when no method available."""
        entry = self.create_entry(message_type="response")
        screen = MessageDetailScreen(entry)

        header = screen._get_header()

        # Method should not appear for responses
        assert "Method:" not in header

    def test_init_stores_entry(self):
        """Test that init stores the entry."""
        entry = self.create_entry()
        screen = MessageDetailScreen(entry)

        assert screen.entry == entry
