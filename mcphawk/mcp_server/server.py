"""MCP server implementation for MCPHawk."""

import json
from typing import Any, Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

from .. import logger
from ..utils import get_message_type


class MCPHawkServer:
    """MCP server that exposes captured traffic data."""

    def __init__(self, db_path: Optional[str] = None):
        self.server = Server("mcphawk-mcp")
        if db_path:
            logger.set_db_path(db_path)
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup MCP protocol handlers."""

        # Store handlers as instance attributes for HTTP transport
        self._handle_list_tools = None
        self._handle_call_tool = None

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="query_traffic",
                    description="Query captured MCP traffic with optional filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 100
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Number of results to skip",
                                "default": 0
                            }
                        }
                    }
                ),
                Tool(
                    name="get_log",
                    description="Get a specific log entry by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "log_id": {
                                "type": "string",
                                "description": "The ID of the log entry to retrieve"
                            }
                        },
                        "required": ["log_id"]
                    }
                ),
                Tool(
                    name="search_traffic",
                    description="Search traffic by message content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Term to search for in message content"
                            },
                            "message_type": {
                                "type": "string",
                                "enum": ["request", "response", "notification"],
                                "description": "Filter by message type"
                            },
                            "traffic_type": {
                                "type": "string",
                                "enum": ["TCP/Direct", "TCP/WS"],
                                "description": "Filter by traffic type"
                            }
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_stats",
                    description="Get statistics about captured traffic",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="list_methods",
                    description="List all unique JSON-RPC methods captured",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]

        # Store the handler
        self._handle_list_tools = handle_list_tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Optional[dict[str, Any]] = None) -> list[TextContent]:
            """Handle tool calls."""

            if name == "query_traffic":
                limit = arguments.get("limit", 100) if arguments else 100
                # offset = arguments.get("offset", 0) if arguments else 0  # TODO: implement offset support
                logs = logger.fetch_logs(limit=limit)

                # Convert datetime objects to strings for JSON serialization
                for log in logs:
                    log["timestamp"] = log["timestamp"].isoformat()

                return [TextContent(type="text", text=json.dumps(logs, indent=2))]

            elif name == "get_log":
                if not arguments or "log_id" not in arguments:
                    return [TextContent(type="text", text="Error: log_id is required")]
                log_id = arguments["log_id"]
                log = logger.get_log_by_id(log_id)
                if log:
                    # Convert datetime to string for JSON serialization
                    log["timestamp"] = log["timestamp"].isoformat()
                    return [TextContent(type="text", text=json.dumps(log, indent=2))]
                else:
                    return [TextContent(type="text", text=f"Error: Log with ID {log_id} not found")]

            elif name == "search_traffic":
                if not arguments or "search_term" not in arguments:
                    return [TextContent(type="text", text="Error: search_term is required")]

                search_term = arguments["search_term"].lower()
                message_type = arguments.get("message_type")
                traffic_type = arguments.get("traffic_type")

                # Fetch all logs and filter (TODO: Add DB-level search)
                all_logs = logger.fetch_logs(limit=1000)
                results = []

                for log in all_logs:
                    if search_term in log["message"].lower():
                        # Apply filters
                        if message_type:
                            log_msg_type = get_message_type(log["message"])
                            if log_msg_type != message_type:
                                continue
                        if traffic_type and log.get("traffic_type") != traffic_type:
                            continue
                        results.append(log)

                # Convert datetime objects to strings
                for log in results:
                    log["timestamp"] = log["timestamp"].isoformat()

                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "get_stats":
                logs = logger.fetch_logs(limit=10000)  # Get recent logs

                stats = {
                    "total": len(logs),
                    "requests": 0,
                    "responses": 0,
                    "notifications": 0,
                    "errors": 0,
                    "by_traffic_type": {
                        "TCP/Direct": 0,
                        "TCP/WS": 0,
                        "N/A": 0
                    }
                }

                for log in logs:
                    msg_type = get_message_type(log["message"])
                    if msg_type == "request":
                        stats["requests"] += 1
                    elif msg_type == "response":
                        stats["responses"] += 1
                    elif msg_type == "notification":
                        stats["notifications"] += 1

                    # Check for errors
                    try:
                        parsed = json.loads(log["message"])
                        if "error" in parsed:
                            stats["errors"] += 1
                    except json.JSONDecodeError:
                        pass

                    # Traffic type
                    traffic_type = log.get("traffic_type", "N/A")
                    if traffic_type in stats["by_traffic_type"]:
                        stats["by_traffic_type"][traffic_type] += 1

                return [TextContent(type="text", text=json.dumps(stats, indent=2))]

            elif name == "list_methods":
                logs = logger.fetch_logs(limit=10000)
                methods = set()

                for log in logs:
                    try:
                        parsed = json.loads(log["message"])
                        if "method" in parsed:
                            methods.add(parsed["method"])
                    except json.JSONDecodeError:
                        pass

                return [TextContent(type="text", text=json.dumps(sorted(methods), indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        # Store the handler
        self._handle_call_tool = handle_call_tool

    async def run_stdio(self):
        """Run the MCP server using stdio transport."""
        import sys

        import anyio
        from mcp.server.stdio import stdio_server

        # Wrap stdin/stdout in async file objects
        async_stdin = anyio.wrap_file(sys.stdin)
        async_stdout = anyio.wrap_file(sys.stdout)

        async with stdio_server(async_stdin, async_stdout) as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

    async def run_http(self, host: str = "127.0.0.1", port: int = 8765):
        """Run the MCP server using Streamable HTTP transport."""
        import uuid

        import uvicorn
        from fastapi import FastAPI, Request, Response
        from fastapi.responses import JSONResponse

        # Create FastAPI app for HTTP transport
        app = FastAPI(title="MCPHawk MCP Server")

        # Store active sessions
        sessions = {}

        # Get handlers for use in closures
        handle_list_tools = self._handle_list_tools
        handle_call_tool = self._handle_call_tool

        @app.post("/mcp")
        async def handle_mcp_request(request: Request):
            """Handle MCP JSON-RPC requests over HTTP."""
            try:
                # Get request body
                body = await request.json()

                # Get or create session ID from headers
                session_id = request.headers.get("X-Session-Id", str(uuid.uuid4()))

                # Process the JSON-RPC request
                method = body.get("method")
                params = body.get("params", {})
                
                # Check if this is a notification (no 'id' field)
                if 'id' not in body:
                    # This is a notification - process it but don't send a response
                    # JSON-RPC 2.0 spec: notifications must not receive any response
                    return Response(status_code=204)
                
                request_id = body.get("id")

                # Handle different methods
                if method == "initialize":
                    # Mark session as initialized
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
                    # Check if session is initialized
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

                    # Get tools list - call our handler directly
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
                    # Check if session is initialized
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

                    # Call the tool
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})

                    # Call our handler directly
                    content = await handle_call_tool(tool_name, tool_args)

                    result = {
                        "content": [
                            {"type": c.type, "text": c.text}
                            for c in content
                        ]
                    }

                else:
                    # Unknown method
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

                # Return successful response
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

                # Include session ID in response headers
                return JSONResponse(
                    content=response,
                    headers={"X-Session-Id": session_id}
                )

            except Exception as e:
                import traceback
                return JSONResponse(
                    status_code=200,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id") if "body" in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e) + "\n" + traceback.format_exc()
                        }
                    }
                )

        # Run the server
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=False
        )
        server = uvicorn.Server(config)
        await server.serve()
