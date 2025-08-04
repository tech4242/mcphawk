"""Integration tests for MCP stdio transport."""

import contextlib
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from mcphawk import logger


class TestMCPStdioIntegration:
    """Test MCP server stdio transport with real subprocess communication."""

    @pytest.fixture
    def test_db(self, tmp_path, monkeypatch):
        """Create a temporary test database and patch the logger to use it."""
        # Create temp database
        db_path = tmp_path / "test_stdio.db"

        # Monkeypatch the logger module to use our test database
        monkeypatch.setattr(logger, "DB_PATH", str(db_path))
        logger.init_db()

        # Add some test data
        test_messages = [
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "test-1"
            },
            {
                "jsonrpc": "2.0",
                "result": {"tools": ["test"]},
                "id": "test-1"
            }
        ]

        for i, msg in enumerate(test_messages):
            entry = {
                "log_id": f"test-{i}",
                "timestamp": datetime.now(tz=timezone.utc),
                "src_ip": "127.0.0.1",
                "dst_ip": "127.0.0.1",
                "src_port": 3000,
                "dst_port": 8000,
                "direction": "unknown",
                "message": json.dumps(msg),
                "transport_type": "unknown"
            }
            logger.log_message(entry)

        return db_path

    def test_stdio_initialize_handshake(self, test_db, monkeypatch):
        """Test proper MCP initialization handshake over stdio."""
        # For this test, we'll use the simpler approach without database dependency
        # The key is to test the protocol handshake works correctly

        # Prepare all requests
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }
        ]

        input_data = "\n".join(json.dumps(req) for req in requests) + "\n"

        # Start the MCP server
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcphawk.cli", "mcp", "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = proc.communicate(input=input_data, timeout=5)

        # Parse responses
        responses = []
        for line in stdout.strip().split('\n'):
            if line:
                with contextlib.suppress(json.JSONDecodeError):
                    responses.append(json.loads(line))

        # Should have at least 2 responses (no response for notification)
        assert len(responses) >= 2, f"Expected at least 2 responses, got {len(responses)}"

        # Check initialize response
        assert responses[0]["id"] == 1
        assert "result" in responses[0]
        assert responses[0]["result"]["protocolVersion"] == "2024-11-05"
        assert responses[0]["result"]["serverInfo"]["name"] == "mcphawk-mcp"

        # Check tools/list response
        assert responses[1]["id"] == 2
        assert "result" in responses[1]
        assert "tools" in responses[1]["result"]
        assert len(responses[1]["result"]["tools"]) == 5  # We have 5 tools

    def test_stdio_basic_communication(self):
        """Test basic stdio communication without select."""
        # Use communicate() for simpler testing
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }
        ]

        input_data = "\n".join(json.dumps(req) for req in requests) + "\n"

        proc = subprocess.Popen(
            [sys.executable, "-m", "mcphawk.cli", "mcp", "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )

        stdout, stderr = proc.communicate(input=input_data, timeout=5)

        # Parse responses
        responses = []
        for line in stdout.strip().split('\n'):
            if line:
                with contextlib.suppress(json.JSONDecodeError):
                    responses.append(json.loads(line))

        # Debug output
        if not responses:
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")

        # Should have 2 responses (no response for notification)
        assert len(responses) >= 2, f"Expected at least 2 responses, got {len(responses)}"

        # Check initialize response
        assert responses[0]["id"] == 1
        assert responses[0]["result"]["protocolVersion"] == "2024-11-05"

        # Check tools/list response
        assert responses[1]["id"] == 2
        assert "tools" in responses[1]["result"]

    def test_stdio_logging_to_stderr(self):
        """Test that all logging goes to stderr, not stdout."""
        # Use communicate for simpler test
        input_data = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            },
            "id": 1
        }) + "\n"

        proc = subprocess.Popen(
            [sys.executable, "-m", "mcphawk.cli", "mcp", "--transport", "stdio", "--debug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = proc.communicate(input=input_data, timeout=5)

        # Response should be valid JSON (no log messages mixed in stdout)
        response_line = stdout.strip()
        response = json.loads(response_line)
        assert response["id"] == 1
        assert "result" in response

        # Check stderr has log messages
        assert "[MCPHawk]" in stderr
        assert "Starting MCP server" in stderr

    @pytest.mark.parametrize("tool_name,args,expected_in_result", [
        ("get_stats", {}, "total"),
        ("list_methods", {}, []),  # Empty list if no data
    ])
    def test_stdio_tool_calls_basic(self, tool_name, args, expected_in_result):
        """Test basic tool calls that don't require specific data."""
        # Use communicate for simpler test
        requests = [
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            },
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            },
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": args
                },
                "id": 2
            }
        ]

        input_data = "\n".join(json.dumps(req) for req in requests) + "\n"

        proc = subprocess.Popen(
            [sys.executable, "-m", "mcphawk.cli", "mcp", "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = proc.communicate(input=input_data, timeout=5)

        # Parse responses
        responses = []
        for line in stdout.strip().split('\n'):
            if line:
                with contextlib.suppress(json.JSONDecodeError):
                    responses.append(json.loads(line))

        # Should have 2 responses (init and tool call)
        assert len(responses) >= 2

        # Check tool response
        tool_response = responses[-1]  # Last response should be tool call
        assert tool_response["id"] == 2
        assert "result" in tool_response
        assert "content" in tool_response["result"]

        # Check content
        content = tool_response["result"]["content"][0]["text"]
        if isinstance(expected_in_result, str):
            assert expected_in_result in content
        else:
            # For list_methods, just check it's valid JSON
            json.loads(content)
