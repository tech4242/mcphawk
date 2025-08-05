"""MCP server implementation using SDK's built-in HTTP transport."""

import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .. import logger as mcphawk_logger

# Set up logging
logger = logging.getLogger(__name__)


class MCPHawkServer:
    """MCP server using SDK's HTTP transport."""

    def __init__(self, db_path: Optional[str] = None, host: str = "127.0.0.1", port: int = 8765):
        # Store configuration
        self.http_host = host
        self.http_port = port

        # FastMCP accepts host and port in constructor
        self.mcp = FastMCP("mcphawk-mcp", host=host, port=port)
        if db_path:
            mcphawk_logger.set_db_path(db_path)
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup MCP protocol handlers."""

        @self.mcp.tool()
        async def query_traffic(limit: int = 100, offset: int = 0) -> str:
            """Query captured MCP traffic with optional limit and offset."""
            logs = mcphawk_logger.fetch_logs_with_offset(limit=limit, offset=offset)

            # Convert timestamps to ISO format for JSON serialization
            for log in logs:
                if log.get("timestamp"):
                    log["timestamp"] = log["timestamp"].isoformat()

            return json.dumps(logs, indent=2)

        @self.mcp.tool()
        async def get_log(log_id: str) -> str:
            """Get a specific log entry by ID."""
            log = mcphawk_logger.get_log_by_id(log_id)

            if not log:
                return f"No log found with ID: {log_id}"

            # Convert timestamp to ISO format
            if log.get("timestamp"):
                log["timestamp"] = log["timestamp"].isoformat()

            return json.dumps(log, indent=2)

        @self.mcp.tool()
        async def search_traffic(
            search_term: str = "",
            message_type: Optional[str] = None,
            transport_type: Optional[str] = None,
            limit: int = 100
        ) -> str:
            """Search traffic by message content or type.

            Args:
                search_term: Term to search for in message content
                message_type: Filter by message type (request, response, notification)
                transport_type: Filter by transport type (streamable_http/http_sse/stdio/unknown)
                limit: Maximum number of results
            """
            logs = mcphawk_logger.search_logs(
                search_term=search_term,
                message_type=message_type,
                transport_type=transport_type,
                limit=limit
            )

            # Convert timestamps to ISO format for JSON serialization
            for log in logs:
                if log.get("timestamp"):
                    log["timestamp"] = log["timestamp"].isoformat()

            return json.dumps(logs, indent=2)

        @self.mcp.tool()
        async def get_stats() -> str:
            """Get statistics about captured traffic."""
            stats = mcphawk_logger.get_traffic_stats()
            return json.dumps(stats, indent=2)

        @self.mcp.tool()
        async def list_methods() -> str:
            """List all unique JSON-RPC methods seen in traffic."""
            methods = mcphawk_logger.get_unique_methods()

            result = {
                "methods": methods,
                "count": len(methods)
            }

            return json.dumps(result, indent=2)

    async def run_stdio(self):
        """Run the MCP server using stdio transport."""
        await self.mcp.run_stdio_async()

    async def run_http(self, host: str = "127.0.0.1", port: int = 8765):
        """Run the MCP server using SDK's Streamable HTTP transport."""
        # If different host/port specified, we need to recreate FastMCP
        if host != self.http_host or port != self.http_port:
            self.http_host = host
            self.http_port = port
            # Recreate FastMCP with new settings
            self.mcp = FastMCP("mcphawk-mcp", host=host, port=port)
            self._setup_handlers()

        # The SDK handles all the HTTP server setup internally
        await self.mcp.run_streamable_http_async()

