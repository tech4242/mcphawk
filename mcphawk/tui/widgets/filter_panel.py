"""Filter panel widget."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Select, Static


class FilterPanel(Vertical):
    """Panel with filter controls."""

    class FilterChanged(Message):
        """Message sent when filters change."""

        def __init__(
            self,
            type_filter: str | None,
            transport_filter: str | None,
            server_filter: str | None,
            search_query: str,
        ):
            super().__init__()
            self.type_filter = type_filter
            self.transport_filter = transport_filter
            self.server_filter = server_filter
            self.search_query = search_query

    def __init__(self, **kwargs):
        """Initialize the filter panel."""
        super().__init__(**kwargs)
        self.type_filter: str | None = None
        self.transport_filter: str | None = None
        self.server_filter: str | None = None
        self.search_query: str = ""

    def compose(self) -> ComposeResult:
        """Compose the filter panel."""
        yield Static("Filters", classes="filter-title")

        yield Static("Type:", classes="filter-label")
        yield Select(
            [
                ("All", None),
                ("Request", "request"),
                ("Response", "response"),
                ("Notification", "notification"),
                ("Error", "error"),
            ],
            id="type-filter",
            allow_blank=False,
            value=None,
        )

        yield Static("Transport:", classes="filter-label")
        yield Select(
            [
                ("All", None),
                ("HTTP", "streamable_http"),
                ("SSE", "http_sse"),
                ("stdio", "stdio"),
            ],
            id="transport-filter",
            allow_blank=False,
            value=None,
        )

        yield Static("Search:", classes="filter-label")
        yield Input(placeholder="Search messages...", id="search-input")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle filter selection changes."""
        if event.select.id == "type-filter":
            self.type_filter = event.value
        elif event.select.id == "transport-filter":
            self.transport_filter = event.value

        self._emit_filter_changed()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_query = event.value
            self._emit_filter_changed()

    def _emit_filter_changed(self) -> None:
        """Emit filter changed message."""
        self.post_message(
            self.FilterChanged(
                type_filter=self.type_filter,
                transport_filter=self.transport_filter,
                server_filter=self.server_filter,
                search_query=self.search_query,
            )
        )

    def focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
