"""Main screen for MCPHawk TUI."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from mcphawk.tui.data.log_manager import LogManager
from mcphawk.tui.logo import LOGO
from mcphawk.tui.widgets.filter_panel import FilterPanel
from mcphawk.tui.widgets.log_table import LogDataTable
from mcphawk.tui.widgets.stats_bar import StatsBar

WELCOME_MESSAGE = f"""{LOGO}
[dim]Press [bold]q[/] to quit • [bold]f[/] to toggle filters • [bold]/[/] to search[/]

[bold cyan]Getting Started:[/]
  [dim]•[/] Run [bold green]mcphawk sniff --port 3000[/] to capture HTTP traffic
  [dim]•[/] Run [bold green]mcphawk wrap /path/to/server[/] to capture stdio traffic
  [dim]•[/] Traffic will appear here automatically
"""


class MainScreen(Screen):
    """Main screen with log table and filters."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("r", "refresh", "Refresh"),
        ("c", "clear", "Clear"),
    ]

    def __init__(self, **kwargs):
        """Initialize the main screen."""
        super().__init__(**kwargs)
        self.log_manager = LogManager()
        self.filter_visible = True

    def compose(self) -> ComposeResult:
        """Compose the main screen layout."""
        yield Header()

        # Welcome banner (shown when no data)
        yield Static(WELCOME_MESSAGE, id="welcome-banner", markup=True)

        # Main content (hidden initially)
        with Horizontal(id="main-container"):
            yield FilterPanel(id="filter-panel")

            with Vertical(id="content-area"):
                yield StatsBar(id="stats-bar")
                yield LogDataTable(id="log-table")

        yield Static("Waiting for traffic...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up polling when screen mounts."""
        # Initially hide main container, show welcome
        self.query_one("#main-container").display = False
        self.query_one("#welcome-banner").display = True

        # Poll every 500ms for new log entries
        self.set_interval(0.5, self._poll_logs)

        # Initial load
        self._poll_logs()

    def _poll_logs(self) -> None:
        """Poll for new log entries."""
        new_entries = self.log_manager.poll_for_updates()

        if new_entries:
            # Switch from welcome to main view on first data
            welcome = self.query_one("#welcome-banner")
            if welcome.display:
                welcome.display = False
                self.query_one("#main-container").display = True

            table = self.query_one("#log-table", LogDataTable)
            for entry in new_entries:
                # Check if entry passes filters
                if self._entry_passes_filters(entry):
                    table.add_log_entry(entry)

            # Update stats
            stats_bar = self.query_one("#stats-bar", StatsBar)
            stats_bar.update_stats(self.log_manager.stats)

            # Update status with count
            status = self.query_one("#status-bar", Static)
            total = self.log_manager.stats.total
            status.update(f"Capturing... Total: {total} messages")

    def _entry_passes_filters(self, entry) -> bool:
        """Check if entry passes current filters."""
        lm = self.log_manager

        if lm.type_filter and entry.message_type != lm.type_filter:
            return False
        if lm.transport_filter and entry.transport_type != lm.transport_filter:
            return False
        if lm.server_filter and entry.server_name != lm.server_filter:
            return False
        if lm.search_query:
            query = lm.search_query.lower()
            if query not in entry.message.lower():
                return False

        return True

    def on_filter_panel_filter_changed(
        self, event: FilterPanel.FilterChanged
    ) -> None:
        """Handle filter changes."""
        self.log_manager.type_filter = event.type_filter
        self.log_manager.transport_filter = event.transport_filter
        self.log_manager.server_filter = event.server_filter
        self.log_manager.search_query = event.search_query

        # Refresh the table with filtered entries
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the table with filtered entries."""
        table = self.query_one("#log-table", LogDataTable)
        table.clear_entries()

        for entry in self.log_manager.get_filtered_entries():
            table.add_log_entry(entry)

    def on_data_table_row_selected(self, event: LogDataTable.RowSelected) -> None:
        """Handle row selection - show message details."""
        if event.row_key:
            entry_id = int(event.row_key.value)
            # Find the entry
            for entry in self.log_manager.entries:
                if entry.id == entry_id:
                    self.app.push_screen("detail", entry)
                    break

    def toggle_filter_panel(self) -> None:
        """Toggle filter panel visibility."""
        panel = self.query_one("#filter-panel", FilterPanel)
        self.filter_visible = not self.filter_visible
        panel.display = self.filter_visible

    def focus_search(self) -> None:
        """Focus the search input."""
        panel = self.query_one("#filter-panel", FilterPanel)
        if not self.filter_visible:
            self.filter_visible = True
            panel.display = True
        panel.focus_search()

    def action_refresh(self) -> None:
        """Force refresh."""
        self._poll_logs()
        self.notify("Refreshed")

    def action_clear(self) -> None:
        """Clear all entries."""
        self.log_manager.clear()
        table = self.query_one("#log-table", LogDataTable)
        table.clear_entries()
        stats_bar = self.query_one("#stats-bar", StatsBar)
        stats_bar.update_stats(self.log_manager.stats)
        self.notify("Cleared")
