"""MCP transport detection logic."""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class MCPTransport(Enum):
    """MCP transport types."""
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"  # Single endpoint, 2025-03-26+
    HTTP_SSE = "http_sse"  # Separate endpoints, deprecated
    UNKNOWN = "unknown"


def detect_transport_from_http(
    method: str,
    path: str,
    headers: dict[str, str],
    is_sse_response: bool = False,
    response_contains_endpoint_event: bool = False
) -> MCPTransport:
    """
    Detect MCP transport type from HTTP traffic.

    HTTP+SSE (legacy):
    - GET request with Accept: text/event-stream
    - Server sends "endpoint" event with POST URL
    - Separate endpoints for SSE and POST
    - POST requests don't have special Accept headers

    Streamable HTTP:
    - POST requests with Accept: application/json, text/event-stream (BOTH required)
    - Single endpoint for all requests
    - No "endpoint" event
    - Dynamic SSE upgrade when needed

    Key differences in Accept headers:
    - HTTP+SSE: GET with Accept: text/event-stream (single type)
    - Streamable HTTP: POST with Accept: application/json, text/event-stream (dual types)

    Args:
        method: HTTP method (GET, POST)
        path: HTTP path
        headers: HTTP headers
        is_sse_response: Whether response has SSE content-type
        response_contains_endpoint_event: Whether SSE stream contains endpoint event

    Returns:
        Detected MCP transport type
    """
    # HTTP+SSE: GET with Accept: text/event-stream (single type)
    if method == "GET" and headers.get("accept", "").lower() == "text/event-stream":
        # This is HTTP+SSE establishing SSE connection
        if response_contains_endpoint_event:
            logger.debug("Detected HTTP+SSE transport (endpoint event found)")
            return MCPTransport.HTTP_SSE
        # Could still be HTTP+SSE without seeing the response yet
        logger.debug("Possible HTTP+SSE transport (GET with SSE accept)")
        return MCPTransport.HTTP_SSE

    # Streamable HTTP: POST with Accept: application/json, text/event-stream (BOTH types)
    accept_header = headers.get("accept", "").lower()
    if method == "POST" and "application/json" in accept_header and "text/event-stream" in accept_header:
        logger.debug("Detected Streamable HTTP transport (POST with dual accept)")
        return MCPTransport.STREAMABLE_HTTP

    # POST without proper dual Accept headers cannot be identified
    # It could be either:
    # - Streamable HTTP missing Accept headers (incorrect client)
    # - HTTP+SSE posting to the endpoint URL (correct behavior)

    # If we see SSE response without prior transport detection, make best guess
    if is_sse_response:
        # In Streamable HTTP, SSE is a response to POST
        # In HTTP+SSE, SSE is response to GET
        logger.debug(f"SSE response detected, method was {method}")
        if method == "POST":
            return MCPTransport.STREAMABLE_HTTP
        else:
            return MCPTransport.HTTP_SSE

    logger.debug("Unable to definitively detect transport type")
    return MCPTransport.UNKNOWN


def extract_endpoint_from_sse(sse_data: str) -> Optional[str]:
    """
    Extract endpoint URL from SSE data (for HTTP+SSE transport).

    The endpoint event in HTTP+SSE looks like:
    event: endpoint
    data: {"url": "http://localhost:8080/messages"}

    Args:
        sse_data: SSE message data

    Returns:
        Endpoint URL if found, None otherwise
    """
    import json

    lines = sse_data.strip().split('\n')
    event_type = None
    data_content = None

    for line in lines:
        if line.startswith('event:'):
            event_type = line[6:].strip()
        elif line.startswith('data:'):
            data_content = line[5:].strip()

    if event_type == "endpoint" and data_content:
        try:
            data = json.loads(data_content)
            return data.get("url")
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse endpoint data: {data_content}")

    return None


class TransportTracker:
    """Track transport type per connection and server."""

    def __init__(self):
        self.transports: dict[tuple[str, int, str, int], MCPTransport] = {}
        self.endpoint_urls: dict[tuple[str, int, str, int], str] = {}
        # Track HTTP+SSE servers by IP:port
        self.http_sse_servers: dict[tuple[str, int], MCPTransport] = {}

    def update_transport(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        transport: MCPTransport
    ) -> None:
        """Update transport type for a connection."""
        key = (src_ip, src_port, dst_ip, dst_port)
        # Also store reverse direction
        reverse_key = (dst_ip, dst_port, src_ip, src_port)

        if transport != MCPTransport.UNKNOWN:
            self.transports[key] = transport
            self.transports[reverse_key] = transport
            logger.debug(f"Updated transport for {key}: {transport.value}")

            # For HTTP+SSE, also track the server endpoint
            if transport == MCPTransport.HTTP_SSE:
                server_key = (dst_ip, dst_port)
                self.http_sse_servers[server_key] = transport
                logger.debug(f"Marked server {dst_ip}:{dst_port} as HTTP+SSE")

    def get_transport(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int
    ) -> MCPTransport:
        """Get transport type for a connection."""
        key = (src_ip, src_port, dst_ip, dst_port)

        # First check if we have transport for this exact connection
        if key in self.transports:
            return self.transports[key]

        # For HTTP+SSE, check if the destination OR source is a known HTTP+SSE server
        dst_server_key = (dst_ip, dst_port)
        if dst_server_key in self.http_sse_servers:
            logger.debug(f"Found HTTP+SSE server {dst_ip}:{dst_port} for new connection")
            return self.http_sse_servers[dst_server_key]

        # Also check if source is an HTTP+SSE server (for responses)
        src_server_key = (src_ip, src_port)
        if src_server_key in self.http_sse_servers:
            logger.debug(f"Response from HTTP+SSE server {src_ip}:{src_port}")
            return self.http_sse_servers[src_server_key]

        return MCPTransport.UNKNOWN

    def store_endpoint_url(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        endpoint_url: str
    ) -> None:
        """Store endpoint URL for HTTP+SSE transport."""
        key = (src_ip, src_port, dst_ip, dst_port)
        self.endpoint_urls[key] = endpoint_url
        logger.debug(f"Stored endpoint URL for {key}: {endpoint_url}")
