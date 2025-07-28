"""Tests for the MCPHawk CLI."""

import logging
from unittest.mock import patch

from typer.testing import CliRunner

from mcphawk.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that CLI help shows both commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sniff" in result.stdout
    assert "web" in result.stdout
    assert "MCPHawk: Passive MCP traffic sniffer + dashboard" in result.stdout


def test_sniff_command_help():
    """Test sniff command help."""
    result = runner.invoke(app, ["sniff", "--help"])
    assert result.exit_code == 0
    assert "Start sniffing MCP traffic" in result.stdout
    # Check for the actual text that appears (may include ANSI codes)
    assert "-filter" in result.stdout or "--filter" in result.stdout
    assert "-debug" in result.stdout or "--debug" in result.stdout
    assert "Enable debug output" in result.stdout


def test_web_command_help():
    """Test web command help."""
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "Start the MCPHawk dashboard" in result.stdout
    # Check for the actual text that appears (may include ANSI codes)
    assert "sniffer" in result.stdout  # Will match -no-sniffer regardless of ANSI codes
    assert "host" in result.stdout  # Will match --host
    assert "port" in result.stdout  # Will match --port


def test_sniff_command_requires_flags():
    """Test sniff command requires port, filter, or auto-detect."""
    result = runner.invoke(app, ["sniff"])
    assert result.exit_code == 1
    assert "[ERROR] You must specify either --port, --filter, or --auto-detect" in result.stdout
    assert "mcphawk sniff --port 3000" in result.stdout
    assert "mcphawk sniff --filter 'tcp port 3000 or tcp port 3001'" in result.stdout
    assert "mcphawk sniff --auto-detect" in result.stdout


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_with_port(mock_start_sniffer):
    """Test sniff command with port option."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--port", "3000"])
    assert result.exit_code == 0
    assert "[MCPHawk] Starting sniffer with filter: tcp port 3000" in result.stdout
    assert "[MCPHawk] Sniffer stopped." in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 3000", auto_detect=False, debug=False, excluded_ports=[])


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_custom_filter(mock_start_sniffer):
    """Test sniff command with custom filter."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--filter", "tcp port 8080"])
    assert result.exit_code == 0
    assert "[MCPHawk] Starting sniffer with filter: tcp port 8080" in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 8080", auto_detect=False, debug=False, excluded_ports=[])


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_auto_detect(mock_start_sniffer):
    """Test sniff command with auto-detect mode."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--auto-detect"])
    assert result.exit_code == 0
    assert "[MCPHawk] Auto-detect mode: monitoring all TCP traffic for MCP messages" in result.stdout
    assert "[MCPHawk] Starting sniffer with filter: tcp" in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp", auto_detect=True, debug=False, excluded_ports=[])


def test_web_command_requires_flags():
    """Test web command requires port, filter, auto-detect, or no-sniffer."""
    result = runner.invoke(app, ["web"])
    assert result.exit_code == 1
    assert "[ERROR] You must specify either --port, --filter, or --auto-detect (or use --no-sniffer)" in result.stdout
    assert "mcphawk web --port 3000" in result.stdout
    assert "mcphawk web --filter 'tcp port 3000 or tcp port 3001'" in result.stdout
    assert "mcphawk web --auto-detect" in result.stdout
    assert "mcphawk web --no-sniffer" in result.stdout


@patch('mcphawk.cli.run_web')
def test_web_command_with_port(mock_run_web):
    """Test web command with port option."""
    result = runner.invoke(app, ["web", "--port", "3000"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp port 3000", auto_detect=False, debug=False, excluded_ports=[], with_mcp=False)


@patch('mcphawk.cli.run_web')
def test_web_command_no_sniffer(mock_run_web):
    """Test web command with --no-sniffer."""
    result = runner.invoke(app, ["web", "--no-sniffer"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=False, host="127.0.0.1", port=8000, filter_expr=None, auto_detect=False, debug=False, excluded_ports=[], with_mcp=False)


@patch('mcphawk.cli.run_web')
def test_web_command_custom_host_web_port(mock_run_web):
    """Test web command with custom host and web-port."""
    result = runner.invoke(app, ["web", "--port", "3000", "--host", "0.0.0.0", "--web-port", "9000"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="0.0.0.0", port=9000, filter_expr="tcp port 3000", auto_detect=False, debug=False, excluded_ports=[], with_mcp=False)


@patch('mcphawk.cli.run_web')
def test_web_command_with_filter(mock_run_web):
    """Test web command with custom filter."""
    result = runner.invoke(app, ["web", "--filter", "tcp port 8080 or tcp port 8081"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp port 8080 or tcp port 8081", auto_detect=False, debug=False, excluded_ports=[], with_mcp=False)


@patch('mcphawk.cli.run_web')
def test_web_command_auto_detect(mock_run_web):
    """Test web command with auto-detect mode."""
    result = runner.invoke(app, ["web", "--auto-detect"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp", auto_detect=True, debug=False, excluded_ports=[], with_mcp=False)


def test_scapy_warnings_suppressed():
    """Test that Scapy warnings are suppressed."""
    # Import should not produce warnings

    # Check that scapy.runtime logger is set to ERROR level
    scapy_logger = logging.getLogger("scapy.runtime")
    assert scapy_logger.level == logging.ERROR


def test_no_default_command():
    """Test that running mcphawk without a command shows error."""
    result = runner.invoke(app, [])
    assert result.exit_code == 2  # Typer returns 2 for missing command
    # Should show error message
    assert "Missing command" in result.stdout
    assert "Usage:" in result.stdout


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_with_debug_flag(mock_start_sniffer):
    """Test sniff command with debug flag."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()

    result = runner.invoke(app, ["sniff", "--port", "3000", "--debug"])
    assert result.exit_code == 0
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 3000", auto_detect=False, debug=True, excluded_ports=[])


@patch('mcphawk.cli.run_web')
def test_web_command_with_debug_flag(mock_run_web):
    """Test web command with debug flag."""
    result = runner.invoke(app, ["web", "--port", "3000", "--debug"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp port 3000", auto_detect=False, debug=True, excluded_ports=[], with_mcp=False)


@patch('mcphawk.cli.run_web')
@patch('mcphawk.cli.MCPHawkServer')
@patch('mcphawk.cli.threading.Thread')
def test_web_command_with_mcp(mock_thread, mock_mcp_server, mock_run_web):
    """Test web command with MCP server integration."""
    result = runner.invoke(app, ["web", "--port", "3000", "--with-mcp"])
    assert result.exit_code == 0

    # Check MCP server was created
    mock_mcp_server.assert_called_once()

    # Check thread was started
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()

    # Check run_web was called with excluded ports
    mock_run_web.assert_called_once_with(
        sniffer=True,
        host="127.0.0.1",
        port=8000,
        filter_expr="tcp port 3000",
        auto_detect=False,
        debug=False,
        excluded_ports=[8765],  # Default MCP port
        with_mcp=True
    )


def test_mcp_command():
    """Test standalone MCP command."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "Run MCPHawk MCP server standalone" in result.stdout
