"""Tests for the MCPHawk CLI."""

import logging
from unittest.mock import patch

from typer.testing import CliRunner

from mcphawk.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that CLI help shows all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sniff" in result.stdout
    assert "web" in result.stdout
    assert "mcp" in result.stdout
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


def test_mcp_command_help():
    """Test mcp command help."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "Run MCPHawk MCP server" in result.stdout
    assert "--transport" in result.stdout
    assert "--mcp-port" in result.stdout
    assert ("stdio or http" in result.stdout) or ("stdio or tcp" in result.stdout)


def test_mcp_command_stdio_transport():
    """Test mcp command with stdio transport."""
    with patch('mcphawk.cli.MCPHawkServer') as mock_server_class, \
         patch('mcphawk.cli.asyncio.run') as mock_asyncio_run:

        mock_server_instance = mock_server_class.return_value

        result = runner.invoke(app, ["mcp", "--transport", "stdio"])

        # Check output
        assert "[MCPHawk] Starting MCP server (transport: stdio)" in result.stdout
        assert "mcpServers" in result.stdout

        # Verify server was created and run_stdio was called
        mock_server_class.assert_called_once()
        mock_asyncio_run.assert_called_once()

        # Verify that asyncio.run was called with the server's run_stdio method
        assert mock_asyncio_run.called
        # The coroutine passed should be from run_stdio
        assert mock_server_instance.run_stdio.called


def test_mcp_command_http_transport():
    """Test mcp command with HTTP transport."""
    with patch('mcphawk.cli.MCPHawkServer') as mock_server_class, \
         patch('mcphawk.cli.asyncio.run') as mock_asyncio_run:

        mock_server_instance = mock_server_class.return_value

        result = runner.invoke(app, ["mcp", "--transport", "http", "--mcp-port", "8765"])

        # Check output
        assert "[MCPHawk] Starting MCP server (transport: http)" in result.stdout
        assert "http://localhost:8765/mcp" in result.stdout
        assert "curl -X POST" in result.stdout

        # Verify server was created and run_http was called
        mock_server_class.assert_called_once()
        mock_asyncio_run.assert_called_once()

        # Verify that asyncio.run was called with the server's run_http method
        assert mock_asyncio_run.called
        # The coroutine passed should be from run_http
        assert mock_server_instance.run_http.called


def test_mcp_command_unknown_transport():
    """Test mcp command with unknown transport."""
    result = runner.invoke(app, ["mcp", "--transport", "websocket"])
    assert result.exit_code == 1
    assert "[ERROR] Unknown transport: websocket" in result.stdout


def test_sniff_with_mcp_http():
    """Test sniff command with MCP HTTP transport."""
    with patch('mcphawk.cli.start_sniffer') as mock_start_sniffer, \
         patch('mcphawk.cli.MCPHawkServer'), \
         patch('mcphawk.cli.threading.Thread') as mock_thread:

        mock_thread_instance = mock_thread.return_value

        result = runner.invoke(app, [
            "sniff",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "http",
            "--mcp-port", "8765"
        ])

        # Check MCP server startup message
        assert "[MCPHawk] Starting MCP HTTP server on http://localhost:8765/mcp" in result.stdout

        # Verify thread was started for MCP server
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

        # Verify sniffer was called with excluded ports
        mock_start_sniffer.assert_called_once()
        call_args = mock_start_sniffer.call_args[1]
        assert call_args['excluded_ports'] == [8765]


def test_sniff_with_mcp_stdio():
    """Test sniff command with MCP stdio transport."""
    with patch('mcphawk.cli.start_sniffer') as mock_start_sniffer, \
         patch('mcphawk.cli.MCPHawkServer'), \
         patch('mcphawk.cli.threading.Thread'):

        result = runner.invoke(app, [
            "sniff",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "stdio"
        ])

        # Check MCP server startup message
        assert "[MCPHawk] Starting MCP server on stdio" in result.stdout

        # Verify sniffer was called with empty excluded ports
        mock_start_sniffer.assert_called_once()
        call_args = mock_start_sniffer.call_args[1]
        assert call_args['excluded_ports'] == []


def test_web_with_mcp_http():
    """Test web command with MCP HTTP transport."""
    with patch('mcphawk.cli.run_web') as mock_run_web, \
         patch('mcphawk.cli.MCPHawkServer'), \
         patch('mcphawk.cli.threading.Thread'):

        result = runner.invoke(app, [
            "web",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "http",
            "--mcp-port", "8766"
        ])

        # Check MCP server startup message
        assert "[MCPHawk] Starting MCP HTTP server on http://localhost:8766/mcp" in result.stdout

        # Verify web was called with excluded ports
        mock_run_web.assert_called_once()
        call_args = mock_run_web.call_args[1]
        assert call_args['excluded_ports'] == [8766]


def test_mcp_command_custom_port():
    """Test mcp command with custom HTTP port."""
    with patch('mcphawk.cli.MCPHawkServer') as mock_server_class, \
         patch('mcphawk.cli.asyncio.run') as mock_asyncio_run:

        mock_server_instance = mock_server_class.return_value

        result = runner.invoke(app, ["mcp", "--transport", "http", "--mcp-port", "9999"])

        # Check output shows custom port
        assert "[MCPHawk] Starting MCP server (transport: http)" in result.stdout
        assert "http://localhost:9999/mcp" in result.stdout

        # Verify server was created
        mock_server_class.assert_called_once()

        # Verify run_http was called with custom port
        mock_asyncio_run.assert_called_once()
        # Check it was called with port=9999
        assert mock_server_instance.run_http.call_args[1]['port'] == 9999


def test_sniff_with_mcp_custom_port():
    """Test sniff command with MCP on custom port."""
    with patch('mcphawk.cli.start_sniffer') as mock_start_sniffer, \
         patch('mcphawk.cli.MCPHawkServer'), \
         patch('mcphawk.cli.threading.Thread') as mock_thread:

        mock_thread_instance = mock_thread.return_value

        result = runner.invoke(app, [
            "sniff",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "http",
            "--mcp-port", "7777"
        ])

        # Check MCP server startup message with custom port
        assert "[MCPHawk] Starting MCP HTTP server on http://localhost:7777/mcp" in result.stdout

        # Verify thread was started for MCP server
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

        # Verify sniffer was called with custom port excluded
        mock_start_sniffer.assert_called_once()
        call_args = mock_start_sniffer.call_args[1]
        assert call_args['excluded_ports'] == [7777]


def test_mcp_stdio_ignores_port():
    """Test that stdio transport ignores the mcp-port parameter."""
    with patch('mcphawk.cli.MCPHawkServer') as mock_server_class, \
         patch('mcphawk.cli.asyncio.run'):

        mock_server_instance = mock_server_class.return_value

        # Even with --mcp-port specified, stdio should ignore it
        result = runner.invoke(app, ["mcp", "--transport", "stdio", "--mcp-port", "9999"])

        # Check output doesn't mention the port
        assert "[MCPHawk] Starting MCP server (transport: stdio)" in result.stdout
        assert "9999" not in result.stdout
        assert "mcpServers" in result.stdout

        # Verify run_stdio was called (not run_http)
        assert mock_server_instance.run_stdio.called
        assert not mock_server_instance.run_http.called


def test_web_with_mcp_default_vs_custom_port():
    """Test that default port 8765 is used when not specified."""
    with patch('mcphawk.cli.run_web') as mock_run_web, \
         patch('mcphawk.cli.MCPHawkServer') as mock_server_class, \
         patch('mcphawk.cli.threading.Thread') as mock_thread:

        # Test 1: Default port
        result = runner.invoke(app, [
            "web",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "http"
        ])

        assert "[MCPHawk] Starting MCP HTTP server on http://localhost:8765/mcp" in result.stdout
        call_args = mock_run_web.call_args[1]
        assert call_args['excluded_ports'] == [8765]

        # Reset mocks
        mock_run_web.reset_mock()
        mock_server_class.reset_mock()
        mock_thread.reset_mock()

        # Test 2: Custom port
        result = runner.invoke(app, [
            "web",
            "--port", "3000",
            "--with-mcp",
            "--mcp-transport", "http",
            "--mcp-port", "5555"
        ])

        assert "[MCPHawk] Starting MCP HTTP server on http://localhost:5555/mcp" in result.stdout
        call_args = mock_run_web.call_args[1]
        assert call_args['excluded_ports'] == [5555]


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
    # Default MCP transport is HTTP on port 8765
    mock_run_web.assert_called_once_with(
        sniffer=True,
        host="127.0.0.1",
        port=8000,
        filter_expr="tcp port 3000",
        auto_detect=False,
        debug=False,
        excluded_ports=[8765],  # Default HTTP MCP port is excluded
        with_mcp=True
    )


def test_mcp_command():
    """Test standalone MCP command."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "Run MCPHawk MCP server standalone" in result.stdout
