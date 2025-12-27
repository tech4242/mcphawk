"""Message detail screen."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from mcphawk.tui.data.log_manager import LogEntry
from mcphawk.tui.widgets.message_view import MessageView


class MessageDetailScreen(ModalScreen):
    """Modal screen showing full message details."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def __init__(self, entry: LogEntry, **kwargs):
        """Initialize with a log entry.

        Args:
            entry: The log entry to display.
        """
        super().__init__(**kwargs)
        self.entry = entry

    def compose(self) -> ComposeResult:
        """Compose the detail screen."""
        with Vertical(id="detail-container"):
            yield Static(self._get_header(), id="detail-header")
            yield MessageView(self.entry, id="message-view")
            yield Button("Close", id="close-button", variant="primary")

    def _get_header(self) -> str:
        """Get the header text."""
        e = self.entry
        parts = [
            "[bold]Message Details[/]",
            f"Time: {e.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Type: {e.message_type}",
            f"Transport: {e.transport_type}",
        ]

        if e.method:
            parts.append(f"Method: {e.method}")

        if e.server_name:
            parts.append(f"Server: {e.server_name}")

        if e.src_ip and e.dst_ip:
            parts.append(f"Flow: {e.src_ip}:{e.src_port} -> {e.dst_ip}:{e.dst_port}")
        elif e.pid:
            parts.append(f"PID: {e.pid}")

        return "\n".join(parts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-button":
            self.action_close()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()
