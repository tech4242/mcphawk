"""MCPHawk TUI Application."""

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType

from mcphawk.tui.screens.main import MainScreen


class MCPHawkApp(App):
    """Main MCPHawk TUI application."""

    TITLE = "MCPHawk"
    SUB_TITLE = "MCP Traffic Analyzer"
    CSS_PATH = "styles/main.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("/", "search", "Search"),
        Binding("?", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the main screen."""
        yield MainScreen()

    def action_toggle_filter(self) -> None:
        """Toggle the filter panel."""
        main_screen = self.query_one(MainScreen)
        main_screen.toggle_filter_panel()

    def action_search(self) -> None:
        """Focus the search input."""
        main_screen = self.query_one(MainScreen)
        main_screen.focus_search()


def run() -> None:
    """Run the MCPHawk TUI."""
    app = MCPHawkApp()
    app.run()


if __name__ == "__main__":
    run()
