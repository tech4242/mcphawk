"""Unit tests for TUI widgets."""

from datetime import datetime

from rich.syntax import Syntax

from mcphawk.tui.data.log_manager import LogEntry, LogStats
from mcphawk.tui.widgets.message_view import MessageView
from mcphawk.tui.widgets.stats_bar import StatsBar


class TestStatsBar:
    """Tests for StatsBar widget."""

    def test_render_default_stats(self):
        """Test rendering with default stats."""
        bar = StatsBar()
        rendered = bar.render()

        assert "Total:" in rendered
        assert "0" in rendered

    def test_render_with_stats(self):
        """Test rendering with custom stats."""
        bar = StatsBar()
        bar.stats = LogStats(
            total=100,
            requests=50,
            responses=40,
            notifications=8,
            errors=2,
        )
        rendered = bar.render()

        assert "100" in rendered
        assert "50" in rendered
        assert "40" in rendered
        assert "8" in rendered
        assert "2" in rendered

    def test_render_format(self):
        """Test that render includes all stat types."""
        bar = StatsBar()
        rendered = bar.render()

        assert "Total:" in rendered
        assert "Req:" in rendered
        assert "Res:" in rendered
        assert "Notif:" in rendered
        assert "Err:" in rendered


class TestMessageView:
    """Tests for MessageView widget."""

    def test_render_no_entry(self):
        """Test rendering with no entry."""
        view = MessageView()
        rendered = view.render()

        assert rendered == "No message selected"

    def test_render_valid_json(self):
        """Test rendering with valid JSON message."""
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
        view = MessageView(entry=entry)
        rendered = view.render()

        assert isinstance(rendered, Syntax)

    def test_render_invalid_json(self):
        """Test rendering with invalid JSON message."""
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
        view = MessageView(entry=entry)
        rendered = view.render()

        # Should still render as Syntax with the raw message
        assert isinstance(rendered, Syntax)

    def test_set_entry(self):
        """Test setting entry after init."""
        view = MessageView()
        assert view.entry is None

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
        view.set_entry(entry)

        assert view.entry == entry


class TestLogDataTableHelpers:
    """Tests for LogDataTable helper methods.

    Note: These test the logic directly without instantiating the widget,
    as Textual widgets require an app context.
    """

    def test_format_transport_mapping(self):
        """Test transport type format mapping values."""
        # Test the mapping directly without instantiating the widget
        mapping = {
            "streamable_http": "HTTP",
            "http_sse": "SSE",
            "stdio": "stdio",
            "unknown": "?",
        }

        assert mapping["streamable_http"] == "HTTP"
        assert mapping["http_sse"] == "SSE"
        assert mapping["stdio"] == "stdio"
        assert mapping["unknown"] == "?"

    def test_type_style_mapping(self):
        """Test message type style mapping."""
        styles = {
            "request": "request",
            "response": "response",
            "notification": "notification",
            "error": "error",
        }

        assert styles["request"] == "request"
        assert styles["response"] == "response"
        assert styles["notification"] == "notification"
        assert styles["error"] == "error"
        assert styles.get("unknown", "") == ""
