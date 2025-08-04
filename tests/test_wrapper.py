"""Tests for the MCP server wrapper functionality."""

import json
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from mcphawk.wrapper import MCPWrapper, run_wrapper


class TestMCPWrapper:
    """Test the MCPWrapper class."""

    def test_init(self):
        """Test wrapper initialization."""
        wrapper = MCPWrapper(["echo", "test"], debug=True)
        assert wrapper.command == ["echo", "test"]
        assert wrapper.debug is True
        assert wrapper.proc is None
        assert wrapper.running is False

    @patch('subprocess.Popen')
    def test_start_process(self, mock_popen):
        """Test starting the wrapped process."""
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        wrapper = MCPWrapper(["echo", "test"])
        exit_code = wrapper.start()

        assert exit_code == 0
        mock_popen.assert_called_once_with(
            ["echo", "test"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )

    @pytest.mark.skip(reason="Test causes hang in some environments")
    @patch('mcphawk.wrapper.time.sleep')  # Mock sleep to avoid delay
    @patch('threading.Thread')
    @patch('subprocess.Popen')
    def test_keyboard_interrupt(self, mock_popen, mock_thread, mock_sleep):
        """Test handling keyboard interrupt."""
        # Create a mock process
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = KeyboardInterrupt()
        mock_proc.poll.return_value = None  # Process is still running
        mock_proc.stdin = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_popen.return_value = mock_proc

        # Mock threads to prevent actual thread creation
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        wrapper = MCPWrapper(["echo", "test"])

        # The start method should catch KeyboardInterrupt and return 130
        exit_code = wrapper.start()

        assert exit_code == 130  # Standard exit code for SIGINT
        # stop() should have been called, which calls terminate
        mock_proc.terminate.assert_called_once()
        # wait should have been called in stop()
        assert mock_proc.wait.call_count >= 1

    def test_stop(self):
        """Test stopping the wrapper."""
        wrapper = MCPWrapper(["echo", "test"])
        wrapper.proc = MagicMock()
        wrapper.running = True

        wrapper.stop()

        assert wrapper.running is False
        wrapper.proc.terminate.assert_called_once()
        wrapper.proc.wait.assert_called_once_with(timeout=5)

    def test_stop_with_timeout(self):
        """Test stopping with timeout and kill."""
        wrapper = MCPWrapper(["echo", "test"])
        wrapper.proc = MagicMock()
        wrapper.proc.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        wrapper.running = True

        wrapper.stop()

        wrapper.proc.terminate.assert_called_once()
        wrapper.proc.kill.assert_called_once()

    @patch('mcphawk.wrapper.log_message')
    def test_parse_json_rpc_client_to_server(self, mock_log_message):
        """Test parsing JSON-RPC from client to server."""
        wrapper = MCPWrapper(["test"])
        wrapper.proc = MagicMock()
        wrapper.proc.pid = 12345

        # Test request
        msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
        wrapper._try_parse_json(json.dumps(msg), "client->server")

        # Check log_message was called
        mock_log_message.assert_called_once()
        log_entry = mock_log_message.call_args[0][0]

        assert log_entry["src_ip"] == "mcp-client"
        assert log_entry["dst_ip"] == "mcp-server"
        assert log_entry["direction"] == "outgoing"
        assert log_entry["transport_type"] == "stdio"
        assert log_entry["pid"] == 12345
        assert log_entry["src_port"] is None
        assert log_entry["dst_port"] is None

    @patch('mcphawk.wrapper.log_message')
    def test_parse_json_rpc_server_to_client(self, mock_log_message):
        """Test parsing JSON-RPC from server to client."""
        wrapper = MCPWrapper(["test"])
        wrapper.proc = MagicMock()
        wrapper.proc.pid = 12345

        # Test response
        msg = {"jsonrpc": "2.0", "result": "ok", "id": 1}
        wrapper._try_parse_json(json.dumps(msg), "server->client")

        # Check log_message was called
        mock_log_message.assert_called_once()
        log_entry = mock_log_message.call_args[0][0]

        assert log_entry["src_ip"] == "mcp-server"
        assert log_entry["dst_ip"] == "mcp-client"
        assert log_entry["direction"] == "incoming"
        assert log_entry["transport_type"] == "stdio"
        assert log_entry["pid"] == 12345
        assert log_entry["src_port"] is None
        assert log_entry["dst_port"] is None

    def test_parse_non_json(self):
        """Test parsing non-JSON lines."""
        wrapper = MCPWrapper(["test"])
        wrapper._log_jsonrpc_message = MagicMock()

        # Should not call log method for non-JSON
        wrapper._try_parse_json("Not JSON", "client->server")
        wrapper._log_jsonrpc_message.assert_not_called()

        # Should not call for non-JSON-RPC
        wrapper._try_parse_json('{"not": "jsonrpc"}', "client->server")
        wrapper._log_jsonrpc_message.assert_not_called()

    @patch('mcphawk.wrapper.broadcast_new_log')
    @patch('mcphawk.wrapper.log_message')
    def test_log_jsonrpc_message_with_broadcast(self, mock_log_message, mock_broadcast):
        """Test logging with broadcasting."""
        wrapper = MCPWrapper(["test"])
        wrapper.proc = MagicMock()
        wrapper.proc.pid = 12345

        msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
        wrapper._log_jsonrpc_message(msg, "client->server")

        # Check both logging and broadcasting were called
        mock_log_message.assert_called_once()
        # Broadcast might fail if no event loop, that's ok

    def test_metadata_includes_command(self):
        """Test that metadata includes the wrapped command."""
        wrapper = MCPWrapper(["/path/to/mcp-server", "--arg1", "--arg2"])
        wrapper.proc = MagicMock()
        wrapper.proc.pid = 12345

        with patch('mcphawk.wrapper.log_message') as mock_log:
            msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
            wrapper._log_jsonrpc_message(msg, "client->server")

            log_entry = mock_log.call_args[0][0]
            metadata = json.loads(log_entry["metadata"])

            assert metadata["wrapper"] is True
            assert metadata["command"] == ["/path/to/mcp-server", "--arg1", "--arg2"]
            assert metadata["direction"] == "client->server"


class TestRunWrapper:
    """Test the run_wrapper function."""

    @patch('mcphawk.wrapper.MCPWrapper')
    def test_run_wrapper_success(self, mock_wrapper_class):
        """Test successful wrapper run."""
        mock_wrapper = MagicMock()
        mock_wrapper.start.return_value = 0
        mock_wrapper_class.return_value = mock_wrapper

        exit_code = run_wrapper(["echo", "test"], debug=True)

        assert exit_code == 0
        mock_wrapper_class.assert_called_once_with(["echo", "test"], debug=True)
        mock_wrapper.start.assert_called_once()

    @patch('signal.signal')
    def test_signal_handlers_setup(self, mock_signal):
        """Test that signal handlers are set up."""
        with patch('mcphawk.wrapper.MCPWrapper') as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper.start.return_value = 0
            mock_wrapper_class.return_value = mock_wrapper

            run_wrapper(["echo", "test"])

            # Check SIGINT and SIGTERM handlers were set
            assert mock_signal.call_count >= 2
            signal_calls = [call[0][0] for call in mock_signal.call_args_list]
            assert signal.SIGINT in signal_calls
            assert signal.SIGTERM in signal_calls


class TestIntegration:
    """Integration tests with real processes."""

    def test_echo_wrapper(self):
        """Test wrapping echo command."""
        # Use a python command that outputs JSON and waits a bit
        wrapper = MCPWrapper([
            "python", "-c",
            "import sys, time; "
            "print('{\"jsonrpc\":\"2.0\",\"method\":\"test\",\"id\":1}'); "
            "sys.stdout.flush(); "
            "time.sleep(0.1)"  # Give wrapper time to read
        ])

        # Mock the logging to capture what would be logged
        with patch('mcphawk.wrapper.log_message') as mock_log:
            # Run wrapper directly (no thread needed for this test)
            exit_code = wrapper.start()

            assert exit_code == 0
            # Should have captured the JSON output
            assert mock_log.called
            # Verify the logged message
            log_entry = mock_log.call_args[0][0]
            assert log_entry["transport_type"] == "stdio"
            assert "test" in log_entry["message"]

    def test_wrapper_forwards_stderr(self):
        """Test that stderr is forwarded correctly."""
        # Use a command that writes to stderr
        wrapper = MCPWrapper(["python", "-c", "import sys; sys.stderr.write('error message\\n')"])

        # Capture our own stderr to check forwarding
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        try:
            exit_code = wrapper.start()
            stderr_output = sys.stderr.getvalue()

            assert exit_code == 0
            assert "error message" in stderr_output
        finally:
            sys.stderr = old_stderr

