"""Stats bar widget."""

from textual.reactive import reactive
from textual.widgets import Static

from mcphawk.tui.data.log_manager import LogStats


class StatsBar(Static):
    """Status bar showing message statistics."""

    stats: reactive[LogStats] = reactive(LogStats)

    def __init__(self, **kwargs):
        """Initialize the stats bar."""
        super().__init__(**kwargs)
        self.stats = LogStats()

    def render(self) -> str:
        """Render the stats bar."""
        s = self.stats
        return (
            f"[bold]Total:[/] {s.total}  "
            f"[blue]Req:[/] {s.requests}  "
            f"[green]Res:[/] {s.responses}  "
            f"[yellow]Notif:[/] {s.notifications}  "
            f"[red]Err:[/] {s.errors}"
        )

    def update_stats(self, stats: LogStats) -> None:
        """Update the displayed stats."""
        self.stats = stats
        self.refresh()
