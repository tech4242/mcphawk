"""Message detail view widget."""

import json

from rich.syntax import Syntax
from textual.widgets import Static

from mcphawk.tui.data.log_manager import LogEntry


class MessageView(Static):
    """Widget for displaying full message details with syntax highlighting."""

    def __init__(self, entry: LogEntry | None = None, **kwargs):
        """Initialize the message view.

        Args:
            entry: The log entry to display.
        """
        super().__init__(**kwargs)
        self.entry = entry

    def render(self) -> Syntax | str:
        """Render the message with syntax highlighting."""
        if not self.entry:
            return "No message selected"

        # Format the JSON nicely
        try:
            data = json.loads(self.entry.message)
            formatted = json.dumps(data, indent=2)
        except json.JSONDecodeError:
            formatted = self.entry.message

        return Syntax(formatted, "json", theme="monokai", line_numbers=True)

    def set_entry(self, entry: LogEntry) -> None:
        """Set the entry to display."""
        self.entry = entry
        self.refresh()
