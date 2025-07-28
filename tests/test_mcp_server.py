"""Tests for MCP server functionality."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from mcp.types import TextContent

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
            "traffic_type": "TCP/WS" if i % 2 == 0 else "TCP/Direct"
        }
        logger.log_message(entry)

    return log_ids


class TestMCPServer:
    """Test MCP server functionality."""

    def test_server_initialization(self, test_db):
        """Test server initializes correctly."""
        server = MCPHawkServer(str(test_db))
        assert server.server.name == "mcphawk-mcp"

        # Check that handlers were registered
        assert hasattr(server.server, 'list_tools')
        assert hasattr(server.server, 'call_tool')

    @pytest.mark.asyncio
    async def test_list_tools_handler(self, test_db):
        """Test the list_tools handler directly."""
        server = MCPHawkServer(str(test_db))

        # Create a mock server instance to capture the handler
        mock_server = Mock()
        handlers = {}

        def capture_list_tools():
            def decorator(func):
                handlers['list_tools'] = func
                return func
            return decorator

        mock_server.list_tools = capture_list_tools

        # Temporarily replace server and setup handlers
        original_server = server.server
        server.server = mock_server
        server._setup_handlers()
        server.server = original_server

        # Now test the captured handler
        tools = await handlers['list_tools']()

        assert len(tools) == 5
        tool_names = [tool.name for tool in tools]
        assert "query_traffic" in tool_names
        assert "get_log" in tool_names
        assert "search_traffic" in tool_names
        assert "get_stats" in tool_names
        assert "list_methods" in tool_names

        # Check tool schemas
        query_tool = next(t for t in tools if t.name == "query_traffic")
        assert "limit" in query_tool.inputSchema["properties"]
        assert "offset" in query_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_call_tool_handler(self, sample_logs):
        """Test the call_tool handler directly."""
        server = MCPHawkServer()

        # Create a mock server instance to capture the handler
        mock_server = Mock()
        handlers = {}

        def capture_call_tool():
            def decorator(func):
                handlers['call_tool'] = func
                return func
            return decorator

        mock_server.call_tool = capture_call_tool
        mock_server.list_tools = lambda: lambda f: f  # Dummy for list_tools

        # Temporarily replace server and setup handlers
        original_server = server.server
        server.server = mock_server
        server._setup_handlers()
        server.server = original_server

        # Test query_traffic
        result = await handlers['call_tool']("query_traffic", {"limit": 2})
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        data = json.loads(result[0].text)
        assert len(data) == 2
        assert all("log_id" in log for log in data)

        # Test get_log
        result = await handlers['call_tool']("get_log", {"log_id": sample_logs[0]})
        data = json.loads(result[0].text)
        assert data["log_id"] == sample_logs[0]
        assert "tools/list" in data["message"]

        # Test get_log with invalid ID
        result = await handlers['call_tool']("get_log", {"log_id": "invalid"})
        assert "not found" in result[0].text

        # Test search_traffic
        result = await handlers['call_tool']("search_traffic", {"search_term": "tools/list"})
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert "tools/list" in data[0]["message"]

        # Test get_stats
        result = await handlers['call_tool']("get_stats", {})
        stats = json.loads(result[0].text)
        assert stats["total"] == 4
        assert stats["requests"] == 1
        assert stats["responses"] == 1
        assert stats["notifications"] == 1
        assert stats["errors"] == 1

        # Test list_methods
        result = await handlers['call_tool']("list_methods", {})
        methods = json.loads(result[0].text)
        assert len(methods) == 2
        assert "tools/list" in methods
        assert "progress/update" in methods

        # Test unknown tool
        result = await handlers['call_tool']("unknown_tool", {})
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_search_with_filters(self, sample_logs):
        """Test search functionality with various filters."""
        server = MCPHawkServer()

        # Capture handler as before
        mock_server = Mock()
        handlers = {}

        def capture_call_tool():
            def decorator(func):
                handlers['call_tool'] = func
                return func
            return decorator

        mock_server.call_tool = capture_call_tool
        mock_server.list_tools = lambda: lambda f: f

        original_server = server.server
        server.server = mock_server
        server._setup_handlers()
        server.server = original_server

        # Test message type filter
        result = await handlers['call_tool']("search_traffic", {
            "search_term": "jsonrpc",
            "message_type": "notification"
        })
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert "progress/update" in data[0]["message"]

        # Test traffic type filter
        result = await handlers['call_tool']("search_traffic", {
            "search_term": "jsonrpc",
            "traffic_type": "TCP/WS"
        })
        data = json.loads(result[0].text)
        assert len(data) == 2
        assert all(log["traffic_type"] == "TCP/WS" for log in data)

    @pytest.mark.asyncio
    async def test_error_handling(self, test_db):
        """Test error handling in handlers."""
        server = MCPHawkServer(str(test_db))

        # Capture handler
        mock_server = Mock()
        handlers = {}

        def capture_call_tool():
            def decorator(func):
                handlers['call_tool'] = func
                return func
            return decorator

        mock_server.call_tool = capture_call_tool
        mock_server.list_tools = lambda: lambda f: f

        original_server = server.server
        server.server = mock_server
        server._setup_handlers()
        server.server = original_server

        # Test missing required parameter
        result = await handlers['call_tool']("get_log", {})
        assert "log_id is required" in result[0].text

        # Test missing search term
        result = await handlers['call_tool']("search_traffic", {})
        assert "search_term is required" in result[0].text
