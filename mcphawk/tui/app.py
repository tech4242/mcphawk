"""MCPHawk TUI Application."""

from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from mcphawk.tui.screens.main import MainScreen


class MCPHawkApp(App):
    """Main MCPHawk TUI application."""

    TITLE = "MCPHawk"
    SUB_TITLE = "MCP Traffic Analyzer"
    CSS_PATH = "styles/main.tcss"

    SCREENS: ClassVar[dict[str, type]] = {"main": MainScreen}

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("/", "search", "Search"),
        Binding("?", "help", "Help"),
    ]

    def on_mount(self) -> None:
        """Push the main screen when app mounts."""
        self.push_screen("main")

    def action_toggle_filter(self) -> None:
        """Toggle the filter panel."""
        screen = self.screen
        if isinstance(screen, MainScreen):
            screen.toggle_filter_panel()

    def action_search(self) -> None:
        """Focus the search input."""
        screen = self.screen
        if isinstance(screen, MainScreen):
            screen.focus_search()


def run() -> None:
    """Run the MCPHawk TUI."""
    app = MCPHawkApp()
    app.run()


if __name__ == "__main__":
    run()
