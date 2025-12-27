"""Tests for the MCPHawk CLI."""

import logging
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mcphawk.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_init_db():
    """Mock init_db to avoid database issues in tests."""
    with patch("mcphawk.cli.init_db"):
        yield


def test_cli_help():
    """Test that CLI help shows all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sniff" in result.stdout
    assert "wrap" in result.stdout
    assert "MCPHawk" in result.stdout


def test_sniff_command_help():
    """Test sniff command help."""
    result = runner.invoke(app, ["sniff", "--help"])
    assert result.exit_code == 0
    assert "Capture HTTP/SSE MCP traffic" in result.stdout
    assert "filter" in result.stdout.lower()
    assert "debug" in result.stdout.lower()


def test_sniff_command_requires_flags():
    """Test sniff command requires port, filter, or auto-detect."""
    result = runner.invoke(app, ["sniff"])
    assert result.exit_code == 1
    assert "You must specify either --port, --filter, or --auto-detect" in result.stdout
    assert "mcphawk sniff --port 3000" in result.stdout
    assert "mcphawk sniff --auto-detect" in result.stdout


@patch("mcphawk.cli.start_sniffer")
def test_sniff_command_with_port(mock_start_sniffer):
    """Test sniff command with port option."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--port", "3000"])
    assert result.exit_code == 0
    assert "Starting sniffer with filter: tcp port 3000" in result.stdout
    assert "Sniffer stopped." in result.stdout
    mock_start_sniffer.assert_called_once_with(
        filter_expr="tcp port 3000", auto_detect=False, debug=False
    )


@patch("mcphawk.cli.start_sniffer")
def test_sniff_command_custom_filter(mock_start_sniffer):
    """Test sniff command with custom filter."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--filter", "tcp port 8080"])
    assert result.exit_code == 0
    assert "Starting sniffer with filter: tcp port 8080" in result.stdout
    mock_start_sniffer.assert_called_once_with(
        filter_expr="tcp port 8080", auto_detect=False, debug=False
    )


@patch("mcphawk.cli.start_sniffer")
def test_sniff_command_auto_detect(mock_start_sniffer):
    """Test sniff command with auto-detect mode."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--auto-detect"])
    assert result.exit_code == 0
    assert "Auto-detect mode: monitoring all TCP traffic for MCP messages" in result.stdout
    assert "Starting sniffer with filter: tcp" in result.stdout
    mock_start_sniffer.assert_called_once_with(
        filter_expr="tcp", auto_detect=True, debug=False
    )


@patch("mcphawk.cli.start_sniffer")
def test_sniff_command_with_debug_flag(mock_start_sniffer):
    """Test sniff command with debug flag."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--port", "3000", "--debug"])
    assert result.exit_code == 0
    mock_start_sniffer.assert_called_once_with(
        filter_expr="tcp port 3000", auto_detect=False, debug=True
    )


def test_scapy_warnings_suppressed():
    """Test that Scapy warnings are suppressed."""
    scapy_logger = logging.getLogger("scapy.runtime")
    assert scapy_logger.level == logging.ERROR


def test_root_command_launches_tui():
    """Test that running mcphawk without a subcommand launches TUI."""
    with patch("mcphawk.tui.app.MCPHawkApp") as mock_app_class:
        mock_app_instance = mock_app_class.return_value

        runner.invoke(app, [])

        # TUI app should be created and run
        mock_app_class.assert_called_once()
        mock_app_instance.run.assert_called_once()


def test_wrap_command_help():
    """Test wrap command help."""
    result = runner.invoke(app, ["wrap", "--help"])
    assert result.exit_code == 0
    assert "Wrap an MCP server to capture stdio traffic" in result.stdout
    assert "Claude Desktop" in result.stdout or "MCP" in result.stdout


def test_wrap_command_requires_command():
    """Test wrap command requires a command to wrap."""
    result = runner.invoke(app, ["wrap"])
    # Exit code 1 indicates error (no command specified)
    assert result.exit_code == 1


@patch("mcphawk.cli.run_wrapper")
def test_wrap_command_runs_wrapper(mock_run_wrapper):
    """Test wrap command runs the wrapper with provided command."""
    mock_run_wrapper.return_value = 0

    result = runner.invoke(app, ["wrap", "/path/to/server", "--arg1"])

    assert result.exit_code == 0
    mock_run_wrapper.assert_called_once_with(
        ["/path/to/server", "--arg1"], debug=False
    )


@patch("mcphawk.cli.run_wrapper")
def test_wrap_command_with_debug(mock_run_wrapper):
    """Test wrap command with debug flag."""
    mock_run_wrapper.return_value = 0

    result = runner.invoke(app, ["wrap", "--debug", "/path/to/server"])

    assert result.exit_code == 0
    mock_run_wrapper.assert_called_once_with(["/path/to/server"], debug=True)
