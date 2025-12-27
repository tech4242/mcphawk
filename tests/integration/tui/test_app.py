"""Integration tests for TUI app using Textual testing framework."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mcphawk.tui.app import MCPHawkApp
from mcphawk.tui.data.log_manager import LogEntry
from mcphawk.tui.screens.detail import MessageDetailScreen
from mcphawk.tui.screens.main import MainScreen
from mcphawk.tui.widgets.filter_panel import FilterPanel
from mcphawk.tui.widgets.log_table import LogDataTable
from mcphawk.tui.widgets.stats_bar import StatsBar


class TestMCPHawkApp:
    """Integration tests for MCPHawkApp."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection to avoid actual DB access."""
        with patch("mcphawk.tui.data.log_manager.get_db_connection") as mock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cursor
            mock.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock.return_value.__exit__ = MagicMock(return_value=False)
            yield mock

    @pytest.mark.asyncio
    async def test_app_starts(self, mock_db_connection):
        """Test that the app starts correctly."""
        app = MCPHawkApp()
        async with app.run_test():
            # App should have a MainScreen
            main_screen = app.query_one(MainScreen)
            assert main_screen is not None

    @pytest.mark.asyncio
    async def test_app_has_log_table(self, mock_db_connection):
        """Test that app contains a log table."""
        app = MCPHawkApp()
        async with app.run_test():
            table = app.query_one(LogDataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_app_has_stats_bar(self, mock_db_connection):
        """Test that app contains a stats bar."""
        app = MCPHawkApp()
        async with app.run_test():
            stats_bar = app.query_one(StatsBar)
            assert stats_bar is not None

    @pytest.mark.asyncio
    async def test_app_has_filter_panel(self, mock_db_connection):
        """Test that app contains a filter panel."""
        app = MCPHawkApp()
        async with app.run_test():
            filter_panel = app.query_one(FilterPanel)
            assert filter_panel is not None

    @pytest.mark.asyncio
    async def test_quit_keybinding(self, mock_db_connection):
        """Test that q key quits the app."""
        app = MCPHawkApp()
        async with app.run_test() as pilot:
            await pilot.press("q")
            # App should exit after q is pressed

    @pytest.mark.asyncio
    async def test_toggle_filter_keybinding(self, mock_db_connection):
        """Test that f key toggles filter panel."""
        app = MCPHawkApp()
        async with app.run_test() as pilot:
            main_screen = app.query_one(MainScreen)
            initial_visible = main_screen.filter_visible

            await pilot.press("f")

            # Filter visibility should toggle
            assert main_screen.filter_visible != initial_visible


class TestMainScreen:
    """Integration tests for MainScreen."""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection."""
        with patch("mcphawk.tui.data.log_manager.get_db_connection") as mock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cursor
            mock.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock.return_value.__exit__ = MagicMock(return_value=False)
            yield mock

    @pytest.mark.asyncio
    async def test_clear_action(self, mock_db_connection):
        """Test clear action resets the log table."""
        app = MCPHawkApp()
        async with app.run_test() as pilot:
            main_screen = app.query_one(MainScreen)

            # Add a test entry manually
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
            main_screen.log_manager._add_entry(entry)

            # Press c to clear
            await pilot.press("c")

            # Log manager should be cleared
            assert len(main_screen.log_manager.entries) == 0

    @pytest.mark.asyncio
    async def test_refresh_action(self, mock_db_connection):
        """Test refresh action."""
        app = MCPHawkApp()
        async with app.run_test() as pilot:
            # Press r to refresh
            await pilot.press("r")

            # Should complete without error


class TestMessageDetailScreen:
    """Integration tests for MessageDetailScreen."""

    @pytest.fixture
    def sample_entry(self):
        """Create a sample log entry."""
        return LogEntry(
            id=1,
            timestamp=datetime.now(),
            src_ip=None,
            src_port=None,
            dst_ip=None,
            dst_port=None,
            direction="outgoing",
            message='{"jsonrpc":"2.0","method":"tools/list","id":1}',
            transport_type="stdio",
            metadata={"server_name": "test-server"},
            pid=12345,
        )

    @pytest.mark.asyncio
    async def test_detail_screen_can_be_created(self, sample_entry):
        """Test that detail screen can be created with an entry."""
        screen = MessageDetailScreen(sample_entry)

        assert screen.entry == sample_entry
        assert screen.entry.method == "tools/list"
        assert screen.entry.server_name == "test-server"

    @pytest.mark.asyncio
    async def test_detail_screen_header_content(self, sample_entry):
        """Test that detail screen header contains expected info."""
        screen = MessageDetailScreen(sample_entry)
        header = screen._get_header()

        assert "Message Details" in header
        assert "tools/list" in header
        assert "test-server" in header
        assert "stdio" in header
