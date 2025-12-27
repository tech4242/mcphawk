"""Log data table widget."""

from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import DataTable

from mcphawk.tui.data.log_manager import LogEntry


class LogDataTable(DataTable):
    """Data table for displaying MCP log entries."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "select_row", "View Details"),
        Binding("a", "toggle_auto_scroll", "Auto-scroll"),
    ]

    def __init__(self, **kwargs):
        """Initialize the log table."""
        super().__init__(**kwargs)
        self.auto_scroll = True
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Set up table columns."""
        self.add_column("Time", key="time", width=12)
        self.add_column("Type", key="type", width=10)
        self.add_column("Method", key="method", width=20)
        self.add_column("Server", key="server", width=15)
        self.add_column("Transport", key="transport", width=12)
        self.add_column("Direction", key="direction", width=8)

    def add_log_entry(self, entry: LogEntry) -> None:
        """Add a log entry to the table."""
        time_str = entry.timestamp.strftime("%H:%M:%S")
        msg_type = entry.message_type
        method = entry.method or entry.message_id or "-"
        server = entry.server_name or "-"
        transport = self._format_transport(entry.transport_type)
        direction = entry.direction

        self.add_row(
            time_str,
            msg_type,
            method[:20],
            server[:15],
            transport,
            direction,
            key=str(entry.id),
        )

        if self.auto_scroll:
            self.scroll_end(animate=False)

    def _format_transport(self, transport: str) -> str:
        """Format transport type for display."""
        mapping = {
            "streamable_http": "HTTP",
            "http_sse": "SSE",
            "stdio": "stdio",
            "unknown": "?",
        }
        return mapping.get(transport, transport[:10])

    def _get_type_style(self, msg_type: str) -> str:
        """Get style class for message type."""
        styles = {
            "request": "request",
            "response": "response",
            "notification": "notification",
            "error": "error",
        }
        return styles.get(msg_type, "")

    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll behavior."""
        self.auto_scroll = not self.auto_scroll
        self.notify(f"Auto-scroll: {'ON' if self.auto_scroll else 'OFF'}")

    def clear_entries(self) -> None:
        """Clear all entries from the table."""
        self.clear()
