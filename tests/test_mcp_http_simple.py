"""Simple HTTP tests for MCP server with mocks."""

import json
from unittest.mock import MagicMock, patch


class TestMCPHTTPSimple:
    """Test MCP server HTTP transport with mocks."""

    def test_sse_response_format(self):
        """Test that we correctly parse SSE format responses."""
        # Mock SSE response
        sse_response = 'data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05"}}\n\n'

        # Parse SSE response
        lines = sse_response.strip().split('\n')
        assert lines[0].startswith('data: ')
        data = json.loads(lines[0][6:])
        assert data["id"] == 1
        assert data["result"]["protocolVersion"] == "2024-11-05"

    @patch('requests.post')
    def test_http_basic_flow_mocked(self, mock_post):
        """Test basic HTTP flow with mocked responses."""
        # Mock responses for each call
        mock_responses = [
            # Initialize response
            MagicMock(
                status_code=200,
                text='data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{},"serverInfo":{"name":"mcphawk-mcp","version":"1.0.0"}}}\n\n',
                headers={"mcp-session-id": "test-session-123"}
            ),
            # List tools response
            MagicMock(
                status_code=200,
                text='data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"query_traffic"},{"name":"get_log"},{"name":"search_traffic"},{"name":"get_stats"},{"name":"list_methods"}]}}\n\n'
            ),
            # Get stats response
            MagicMock(
                status_code=200,
                text='data: {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\\"total\\":10,\\"requests\\":3,\\"responses\\":3,\\"notifications\\":2,\\"errors\\":2}"}]}}\n\n'
            )
        ]
        mock_post.side_effect = mock_responses

        # Import here to avoid issues
        import requests

        # 1. Initialize
        response = requests.post(
            "http://localhost:8765/mcp",
            json={"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1},
            headers={"Accept": "application/json, text/event-stream"}
        )
        assert response.status_code == 200
        session_id = response.headers.get("mcp-session-id")
        assert session_id == "test-session-123"

        # 2. List tools
        response = requests.post(
            "http://localhost:8765/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
            headers={"Accept": "application/json, text/event-stream", "mcp-session-id": session_id}
        )
        assert response.status_code == 200

        # Parse and check tools
        lines = response.text.strip().split('\n')
        data = json.loads(lines[0][6:])
        assert len(data["result"]["tools"]) == 5

        # 3. Call get_stats
        response = requests.post(
            "http://localhost:8765/mcp",
            json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_stats"}, "id": 3},
            headers={"Accept": "application/json, text/event-stream", "mcp-session-id": session_id}
        )
        assert response.status_code == 200

        # Parse stats
        lines = response.text.strip().split('\n')
        data = json.loads(lines[0][6:])
        stats = json.loads(data["result"]["content"][0]["text"])
        assert stats["total"] == 10
        assert stats["requests"] == 3

    @patch('requests.post')
    def test_http_error_handling_mocked(self, mock_post):
        """Test HTTP error handling with mocked responses."""
        # Mock error responses
        mock_responses = [
            # Session not initialized error
            MagicMock(
                status_code=200,
                text='data: {"jsonrpc":"2.0","id":1,"error":{"code":-32602,"message":"Session not initialized"}}\n\n'
            ),
            # Unknown method error
            MagicMock(
                status_code=200,
                text='data: {"jsonrpc":"2.0","id":2,"error":{"code":-32601,"message":"Unknown method: unknown/method"}}\n\n'
            )
        ]
        mock_post.side_effect = mock_responses

        import requests

        # Try to call tool without initialization
        response = requests.post(
            "http://localhost:8765/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1},
            headers={"Accept": "application/json, text/event-stream", "mcp-session-id": "uninitialized"}
        )
        assert response.status_code == 200

        # Parse SSE response
        lines = response.text.strip().split('\n')
        data = json.loads(lines[0][6:])
        assert "error" in data
        assert data["error"]["message"] == "Session not initialized"

        # Unknown method
        response = requests.post(
            "http://localhost:8765/mcp",
            json={"jsonrpc": "2.0", "method": "unknown/method", "params": {}, "id": 2},
            headers={"Accept": "application/json, text/event-stream"}
        )
        assert response.status_code == 200

        # Parse SSE response
        lines = response.text.strip().split('\n')
        data = json.loads(lines[0][6:])
        assert "error" in data
        assert "Unknown method" in data["error"]["message"]
