"""Tests for MCP server functionality."""

import asyncio
import contextlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from mcphawk import logger
from mcphawk.mcp_server.server import MCPHawkServer


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_mcp.db"
    logger.set_db_path(str(db_path))
    logger.init_db()
    yield db_path


@pytest.fixture
def sample_logs(test_db):
    """Create sample log entries."""
    test_messages = [
        {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "req-1"
        },
        {
            "jsonrpc": "2.0",
            "result": {"tools": ["query", "search"]},
            "id": "req-1"
        },
        {
            "jsonrpc": "2.0",
            "method": "progress/update",
            "params": {"progress": 50}
        },
        {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": "req-2"
        }
    ]

    log_ids = []
    for i, msg in enumerate(test_messages):
        log_id = str(uuid.uuid4())
        log_ids.append(log_id)
        entry = {
            "log_id": log_id,
            "timestamp": datetime.now(tz=timezone.utc),
            "src_ip": "127.0.0.1",
            "dst_ip": "127.0.0.1",
            "src_port": 3000 + i,
            "dst_port": 8000,
            "direction": "unknown",
            "message": json.dumps(msg),
            "traffic_type": "TCP/Direct"
        }
        logger.log_message(entry)

    return log_ids


class TestMCPServer:
    """Test MCP server functionality."""

    def test_server_initialization(self, test_db):
        """Test server initializes correctly."""
        server = MCPHawkServer(str(test_db))
        assert server.mcp.name == "mcphawk-mcp"

        # Check that FastMCP instance was created
        assert hasattr(server, 'mcp')
        assert hasattr(server.mcp, 'tool')

    def test_list_tools(self, test_db):
        """Test that tools are registered correctly."""
        server = MCPHawkServer(str(test_db))

        # The FastMCP instance exposes tools through _tool_manager._tools
        tool_names = list(server.mcp._tool_manager._tools.keys())

        assert len(tool_names) == 5
        assert "query_traffic" in tool_names
        assert "get_log" in tool_names
        assert "search_traffic" in tool_names
        assert "get_stats" in tool_names
        assert "list_methods" in tool_names

    @pytest.mark.asyncio
    async def test_call_tools(self, sample_logs):
        """Test calling tools directly."""
        server = MCPHawkServer()

        # Test query_traffic
        query_tool = server.mcp._tool_manager._tools["query_traffic"]
        result = await query_tool.fn(limit=2, offset=0)
        data = json.loads(result)
        assert len(data) == 2
        assert all("log_id" in log for log in data)

        # Test get_log
        get_log_tool = server.mcp._tool_manager._tools["get_log"]
        result = await get_log_tool.fn(log_id=sample_logs[0])
        data = json.loads(result)
        assert data["log_id"] == sample_logs[0]
        assert "tools/list" in data["message"]

        # Test get_log with invalid ID
        result = await get_log_tool.fn(log_id="invalid")
        assert "No log found" in result

        # Test search_traffic
        search_tool = server.mcp._tool_manager._tools["search_traffic"]
        result = await search_tool.fn(search_term="tools/list")
        data = json.loads(result)
        assert len(data) == 1
        assert "tools/list" in data[0]["message"]

        # Test get_stats
        stats_tool = server.mcp._tool_manager._tools["get_stats"]
        result = await stats_tool.fn()
        stats = json.loads(result)
        assert stats["total_logs"] == 4
        assert stats["requests"] == 1
        assert stats["responses"] == 1
        assert stats["notifications"] == 1
        assert stats["errors"] == 1

        # Test list_methods
        methods_tool = server.mcp._tool_manager._tools["list_methods"]
        result = await methods_tool.fn()
        methods_data = json.loads(result)
        # The result format is {"methods": [...], "count": 2}
        assert methods_data["count"] == 2
        assert "tools/list" in methods_data["methods"]
        assert "progress/update" in methods_data["methods"]

    @pytest.mark.asyncio
    async def test_search_with_filters(self, sample_logs):
        """Test search functionality with various filters."""
        server = MCPHawkServer()

        search_tool = server.mcp._tool_manager._tools["search_traffic"]

        # Test message type filter
        result = await search_tool.fn(
            search_term="jsonrpc",
            message_type="notification"
        )
        data = json.loads(result)
        assert len(data) == 1
        assert "progress/update" in data[0]["message"]

        # Test traffic type filter
        result = await search_tool.fn(
            search_term="jsonrpc",
            traffic_type="TCP/Direct"
        )
        data = json.loads(result)
        # All 4 test messages match the search criteria
        assert len(data) == 4
        assert all(log["traffic_type"] == "TCP/Direct" for log in data)

    @pytest.mark.asyncio
    async def test_error_handling(self, test_db):
        """Test error handling in tool functions."""
        server = MCPHawkServer(str(test_db))

        # The SDK handles parameter validation automatically
        # So we'll test the actual error cases in the tool implementations

        get_log_tool = server.mcp._tool_manager._tools["get_log"]

        # Test with non-existent log ID
        result = await get_log_tool.fn(log_id="non-existent-id")
        assert "No log found with ID" in result

    @pytest.mark.asyncio
    async def test_run_stdio(self):
        """Test that run_stdio properly handles stdio transport."""
        server = MCPHawkServer()

        # Mock the run_stdio_async method to avoid actual stdio operations
        with patch.object(server.mcp, 'run_stdio_async', new_callable=AsyncMock) as mock_run:
            await server.run_stdio()

            # Verify run was called
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_http(self, test_db):
        """Test that run_http properly handles HTTP transport."""
        server = MCPHawkServer(str(test_db))

        # Create test server config that immediately shuts down
        with patch('uvicorn.Server') as mock_server_class:
            mock_server_instance = AsyncMock()
            mock_server_instance.serve = AsyncMock()
            mock_server_class.return_value = mock_server_instance

            # Run the server in a task that we'll cancel
            task = asyncio.create_task(server.run_http(port=8765))

            # Give it a moment to set up
            await asyncio.sleep(0.1)

            # Cancel the task
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

            # Verify uvicorn was configured correctly
            mock_server_class.assert_called_once()
            config = mock_server_class.call_args[0][0]
            assert config.host == "127.0.0.1"
            assert config.port == 8765

    @pytest.mark.asyncio
    async def test_fastmcp_integration(self, sample_logs):
        """Test that FastMCP handles requests correctly."""
        server = MCPHawkServer()

        # Test that we can access tool metadata
        query_tool = server.mcp._tool_manager._tools["query_traffic"]
        assert query_tool.description
        # Tool has parameters but not exposed as input_schema
        assert hasattr(query_tool, 'fn')

        # Test tool execution
        result = await query_tool.fn(limit=1, offset=0)
        data = json.loads(result)
        assert len(data) == 1
        assert "log_id" in data[0]

    @pytest.mark.asyncio
    async def test_notification_handling_concept(self):
        """Test the concept of notification handling (SDK handles the actual protocol)."""
        # The FastMCP SDK handles JSON-RPC protocol details including notifications
        # This test verifies our understanding of the concept

        # In JSON-RPC 2.0:
        # - Requests have an 'id' field and expect a response
        # - Notifications have no 'id' field and should not receive a response

        notification = {
            "jsonrpc": "2.0",
            "method": "progress/update",
            "params": {"progress": 50}
            # Note: no 'id' field
        }

        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1
        }

        # Verify our test data structure
        assert "id" not in notification
        assert "id" in request

