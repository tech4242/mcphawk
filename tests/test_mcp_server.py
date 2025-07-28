"""Tests for MCP server functionality."""

import asyncio
import contextlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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

    @pytest.mark.asyncio
    async def test_run_stdio(self):
        """Test that run_stdio properly handles stdio transport."""
        server = MCPHawkServer()

        # Mock dependencies
        with patch('anyio.wrap_file') as mock_wrap_file, \
             patch('mcp.server.stdio.stdio_server') as mock_stdio_server:

            # Setup mocks
            mock_async_stdin = AsyncMock()
            mock_async_stdout = AsyncMock()
            mock_wrap_file.side_effect = [mock_async_stdin, mock_async_stdout]

            mock_read_stream = AsyncMock()
            mock_write_stream = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = (mock_read_stream, mock_write_stream)
            mock_context.__aexit__.return_value = None
            mock_stdio_server.return_value = mock_context

            # Mock server.run to complete immediately
            server.server.run = AsyncMock()
            server.server.create_initialization_options = MagicMock(return_value={})

            # Run the method
            await server.run_stdio()

            # Verify wrap_file was called correctly
            assert mock_wrap_file.call_count == 2

            # Verify stdio_server was called with wrapped files
            mock_stdio_server.assert_called_once_with(mock_async_stdin, mock_async_stdout)

            # Verify server.run was called
            server.server.run.assert_called_once_with(
                mock_read_stream,
                mock_write_stream,
                {}
            )

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
    async def test_http_handlers(self, sample_logs):
        """Test HTTP transport handlers with actual requests."""
        from fastapi.testclient import TestClient

        # Create a temporary database for this test
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name

        # Initialize database with sample data
        logger.set_db_path(db_path)
        logger.init_db()

        # Re-create sample logs in the new database
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

        for i, msg in enumerate(test_messages):
            entry = {
                "log_id": str(uuid.uuid4()),
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

        # Create server instance
        server = MCPHawkServer(db_path)

        # Get the FastAPI app by running the HTTP server setup
        app = None
        sessions = {}

        # Extract the app creation logic
        import uuid as uuid_module

        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        app = FastAPI(title="MCPHawk MCP Server")

        # Get references to handlers
        handle_list_tools = server._handle_list_tools
        handle_call_tool = server._handle_call_tool

        @app.post("/mcp")
        async def handle_mcp_request(request: Request):
            """Handle MCP JSON-RPC requests over HTTP."""
            try:
                body = await request.json()
                session_id = request.headers.get("X-Session-Id", str(uuid_module.uuid4()))
                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")

                if method == "initialize":
                    sessions[session_id] = True
                    result = {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "experimental": {},
                            "tools": {"listChanged": False}
                        },
                        "serverInfo": {
                            "name": "mcphawk-mcp",
                            "version": "1.12.2"
                        }
                    }

                elif method == "tools/list":
                    if session_id not in sessions:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32602,
                                    "message": "Session not initialized"
                                }
                            }
                        )

                    tools = await handle_list_tools()
                    result = {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in tools
                        ]
                    }

                elif method == "tools/call":
                    if session_id not in sessions:
                        return JSONResponse(
                            status_code=200,
                            content={
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "error": {
                                    "code": -32602,
                                    "message": "Session not initialized"
                                }
                            }
                        )

                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})
                    content = await handle_call_tool(tool_name, tool_args)

                    result = {
                        "content": [
                            {"type": c.type, "text": c.text}
                            for c in content
                        ]
                    }

                else:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Unknown method: {method}"
                            }
                        }
                    )

                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

                return JSONResponse(
                    content=response,
                    headers={"X-Session-Id": session_id}
                )

            except Exception as e:
                return JSONResponse(
                    status_code=200,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id") if "body" in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    }
                )

        # Create test client
        client = TestClient(app)

        # Test initialize
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                },
                "id": 1
            },
            headers={"X-Session-Id": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["protocolVersion"] == "2024-11-05"
        assert "test-session" in sessions

        # Test tools/list without session
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            },
            headers={"X-Session-Id": "new-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["message"] == "Session not initialized"

        # Test tools/list with session
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 3
            },
            headers={"X-Session-Id": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["result"]["tools"]) == 5

        # Test tools/call get_stats
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_stats",
                    "arguments": {}
                },
                "id": 4
            },
            headers={"X-Session-Id": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        stats = json.loads(data["result"]["content"][0]["text"])
        assert stats["total"] == 4

        # Test unknown method
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "params": {},
                "id": 5
            },
            headers={"X-Session-Id": "test-session"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Unknown method" in data["error"]["message"]

        # Clean up
        os.unlink(db_path)
