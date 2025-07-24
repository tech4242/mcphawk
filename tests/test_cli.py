"""Tests for the MCPHawk CLI."""

import logging
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from mcphawk.cli import app
import pytest


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
    assert "--filter" in result.stdout


def test_web_command_help():
    """Test web command help."""
    result = runner.invoke(app, ["web", "--help"])
    assert result.exit_code == 0
    assert "Start the MCPHawk dashboard" in result.stdout
    assert "--no-sniffer" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout


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
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 3000", auto_detect=False)


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_custom_filter(mock_start_sniffer):
    """Test sniff command with custom filter."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["sniff", "--filter", "tcp port 8080"])
    assert result.exit_code == 0
    assert "[MCPHawk] Starting sniffer with filter: tcp port 8080" in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 8080", auto_detect=False)


@patch('mcphawk.cli.start_sniffer')
def test_sniff_command_auto_detect(mock_start_sniffer):
    """Test sniff command with auto-detect mode."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["sniff", "--auto-detect"])
    assert result.exit_code == 0
    assert "[MCPHawk] Auto-detect mode: monitoring all TCP traffic for MCP messages" in result.stdout
    assert "[MCPHawk] Starting sniffer with filter: tcp" in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp", auto_detect=True)


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
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp port 3000", auto_detect=False)


@patch('mcphawk.cli.run_web')
def test_web_command_no_sniffer(mock_run_web):
    """Test web command with --no-sniffer."""
    result = runner.invoke(app, ["web", "--no-sniffer"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=False, host="127.0.0.1", port=8000, filter_expr=None, auto_detect=False)


@patch('mcphawk.cli.run_web')
def test_web_command_custom_host_web_port(mock_run_web):
    """Test web command with custom host and web-port."""
    result = runner.invoke(app, ["web", "--port", "3000", "--host", "0.0.0.0", "--web-port", "9000"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="0.0.0.0", port=9000, filter_expr="tcp port 3000", auto_detect=False)


@patch('mcphawk.cli.run_web')
def test_web_command_with_filter(mock_run_web):
    """Test web command with custom filter."""
    result = runner.invoke(app, ["web", "--filter", "tcp port 8080 or tcp port 8081"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp port 8080 or tcp port 8081", auto_detect=False)


@patch('mcphawk.cli.run_web')
def test_web_command_auto_detect(mock_run_web):
    """Test web command with auto-detect mode."""
    result = runner.invoke(app, ["web", "--auto-detect"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000, filter_expr="tcp", auto_detect=True)


def test_scapy_warnings_suppressed():
    """Test that Scapy warnings are suppressed."""
    # Import should not produce warnings
    import mcphawk.cli
    import mcphawk.sniffer
    
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
