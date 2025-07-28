"""Simple HTTP integration tests for MCP server."""

import json
import subprocess
import sys
import time

import pytest
import requests


class TestMCPHTTPSimple:
    """Test MCP server HTTP transport with subprocess."""

    @pytest.fixture
    def mcp_server_url(self):
        """Start MCP server in subprocess and return URL."""
        # Start server
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcphawk.cli", "mcp", "--transport", "http", "--mcp-port", "8768"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Give server time to start
        time.sleep(2)

        # Check if server started
        assert proc.poll() is None, "Server failed to start"

        yield "http://localhost:8768/mcp"

        # Cleanup
        proc.terminate()
        proc.wait()

    def test_http_basic_flow(self, mcp_server_url):
        """Test basic HTTP flow: initialize, list tools, call tool."""
        session_id = "test-session-basic"

        # 1. Initialize
        response = requests.post(
            mcp_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-http", "version": "1.0"}
                },
                "id": 1
            },
            headers={"X-Session-Id": session_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["result"]["protocolVersion"] == "2024-11-05"

        # 2. List tools
        response = requests.post(
            mcp_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            },
            headers={"X-Session-Id": session_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert len(data["result"]["tools"]) == 5

        # 3. Call get_stats
        response = requests.post(
            mcp_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_stats",
                    "arguments": {}
                },
                "id": 3
            },
            headers={"X-Session-Id": session_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 3
        assert "content" in data["result"]

        # Parse stats
        stats = json.loads(data["result"]["content"][0]["text"])
        assert "total" in stats
        assert "requests" in stats

    def test_http_error_handling(self, mcp_server_url):
        """Test HTTP error handling."""
        # Try to call tool without initialization
        response = requests.post(
            mcp_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 1
            },
            headers={"X-Session-Id": "uninitialized"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "not initialized" in data["error"]["message"]

        # Unknown method
        response = requests.post(
            mcp_server_url,
            json={
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "params": {},
                "id": 2
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Unknown method" in data["error"]["message"]
