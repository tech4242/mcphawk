"""Tests for the MCP-Shark CLI."""

import logging
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from mcp_shark.cli import app
import pytest


runner = CliRunner()


def test_cli_help():
    """Test that CLI help shows both commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "sniff" in result.stdout
    assert "web" in result.stdout
    assert "MCP-Shark: Passive MCP traffic sniffer + dashboard" in result.stdout


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
    assert "Start the MCP-Shark dashboard" in result.stdout
    assert "--no-sniffer" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout


@patch('mcp_shark.cli.start_sniffer')
def test_sniff_command_default_filter(mock_start_sniffer):
    """Test sniff command with default filter."""
    # Simulate KeyboardInterrupt to stop the sniffer
    mock_start_sniffer.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["sniff"])
    assert result.exit_code == 0
    assert "[MCP-Shark] Starting sniffer with filter: tcp and port 12345" in result.stdout
    assert "[MCP-Shark] Sniffer stopped." in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp and port 12345")


@patch('mcp_shark.cli.start_sniffer')
def test_sniff_command_custom_filter(mock_start_sniffer):
    """Test sniff command with custom filter."""
    mock_start_sniffer.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(app, ["sniff", "--filter", "tcp port 8080"])
    assert result.exit_code == 0
    assert "[MCP-Shark] Starting sniffer with filter: tcp port 8080" in result.stdout
    mock_start_sniffer.assert_called_once_with(filter_expr="tcp port 8080")


@patch('mcp_shark.cli.run_web')
def test_web_command_defaults(mock_run_web):
    """Test web command with default parameters."""
    result = runner.invoke(app, ["web"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="127.0.0.1", port=8000)


@patch('mcp_shark.cli.run_web')
def test_web_command_no_sniffer(mock_run_web):
    """Test web command with --no-sniffer."""
    result = runner.invoke(app, ["web", "--no-sniffer"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=False, host="127.0.0.1", port=8000)


@patch('mcp_shark.cli.run_web')
def test_web_command_custom_host_port(mock_run_web):
    """Test web command with custom host and port."""
    result = runner.invoke(app, ["web", "--host", "0.0.0.0", "--port", "9000"])
    assert result.exit_code == 0
    mock_run_web.assert_called_once_with(sniffer=True, host="0.0.0.0", port=9000)


def test_scapy_warnings_suppressed():
    """Test that Scapy warnings are suppressed."""
    # Import should not produce warnings
    import mcp_shark.cli
    import mcp_shark.sniffer
    
    # Check that scapy.runtime logger is set to ERROR level
    scapy_logger = logging.getLogger("scapy.runtime")
    assert scapy_logger.level == logging.ERROR


def test_no_default_command():
    """Test that running mcp-shark without a command shows error."""
    result = runner.invoke(app, [])
    assert result.exit_code == 2  # Typer returns 2 for missing command
    # Should show error message
    assert "Missing command" in result.stdout
    assert "Usage:" in result.stdout
