"""Stats chart widget with bar visualization."""

from textual.reactive import reactive
from textual.widgets import Static

from mcphawk.tui.data.log_manager import LogStats


class StatsChart(Static):
    """Widget showing message type distribution as bar chart."""

    stats: reactive[LogStats] = reactive(LogStats)

    # Bar characters for chart
    FILLED = "█"
    EMPTY = "░"
    BAR_WIDTH = 10

    def __init__(self, **kwargs):
        """Initialize the stats chart."""
        super().__init__(**kwargs)
        self.stats = LogStats()

    def _make_bar(self, value: int, total: int) -> str:
        """Create a bar representation."""
        if total == 0:
            return self.EMPTY * self.BAR_WIDTH

        ratio = value / total
        filled = int(ratio * self.BAR_WIDTH)
        empty = self.BAR_WIDTH - filled
        return self.FILLED * filled + self.EMPTY * empty

    def _pct(self, value: int, total: int) -> str:
        """Calculate percentage string."""
        if total == 0:
            return "  0%"
        pct = int((value / total) * 100)
        return f"{pct:3d}%"

    def render(self) -> str:
        """Render the stats chart."""
        s = self.stats
        total = s.total

        if total == 0:
            return "[dim]No data[/]"

        lines = [
            f"[blue]Req[/] {self._make_bar(s.requests, total)}{self._pct(s.requests, total)}",
            f"[green]Res[/] {self._make_bar(s.responses, total)}{self._pct(s.responses, total)}",
            f"[yellow]Not[/] {self._make_bar(s.notifications, total)}{self._pct(s.notifications, total)}",
            f"[red]Err[/] {self._make_bar(s.errors, total)}{self._pct(s.errors, total)}",
        ]
        return "\n".join(lines)

    def update_stats(self, stats: LogStats) -> None:
        """Update the displayed stats."""
        self.stats = stats
        self.refresh()
