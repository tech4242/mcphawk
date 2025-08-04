"""Test transport detection logic."""


from mcphawk.transport_detector import (
    MCPTransport,
    TransportTracker,
    detect_transport_from_http,
    extract_endpoint_from_sse,
)


class TestTransportDetection:
    """Test MCP transport detection."""

    def test_streamable_http_dual_accept(self):
        """Test Streamable HTTP detection with dual accept headers."""
        transport = detect_transport_from_http(
            method="POST",
            path="/mcp",
            headers={
                "accept": "application/json, text/event-stream",
                "content-type": "application/json"
            }
        )
        assert transport == MCPTransport.STREAMABLE_HTTP

    def test_post_without_accept_headers(self):
        """Test that POST without Accept headers returns UNKNOWN.

        POST to /mcp without proper Accept headers cannot be definitively
        identified as Streamable HTTP. It could be HTTP+SSE posting to
        the endpoint URL.
        """
        transport = detect_transport_from_http(
            method="POST",
            path="/mcp",
            headers={"content-type": "application/json"}
        )
        assert transport == MCPTransport.UNKNOWN

    def test_streamable_http_sse_response_to_post(self):
        """Test Streamable HTTP detection when SSE response to POST."""
        transport = detect_transport_from_http(
            method="POST",
            path="/api",
            headers={"content-type": "application/json"},
            is_sse_response=True
        )
        assert transport == MCPTransport.STREAMABLE_HTTP

    def test_http_sse_get_with_accept(self):
        """Test HTTP+SSE detection with GET and SSE accept header."""
        transport = detect_transport_from_http(
            method="GET",
            path="/sse",
            headers={"accept": "text/event-stream"}
        )
        assert transport == MCPTransport.HTTP_SSE

    def test_http_sse_with_endpoint_event(self):
        """Test HTTP+SSE detection with endpoint event."""
        transport = detect_transport_from_http(
            method="GET",
            path="/sse",
            headers={"accept": "text/event-stream"},
            response_contains_endpoint_event=True
        )
        assert transport == MCPTransport.HTTP_SSE

    def test_http_sse_response_to_get(self):
        """Test HTTP+SSE detection when SSE response to GET."""
        transport = detect_transport_from_http(
            method="GET",
            path="/api",
            headers={},
            is_sse_response=True
        )
        assert transport == MCPTransport.HTTP_SSE

    def test_unknown_regular_http(self):
        """Test unknown transport for regular HTTP."""
        transport = detect_transport_from_http(
            method="POST",
            path="/api",
            headers={"content-type": "application/json"}
        )
        assert transport == MCPTransport.UNKNOWN

    def test_unknown_no_clear_indicators(self):
        """Test unknown transport when no clear indicators."""
        transport = detect_transport_from_http(
            method="GET",
            path="/api",
            headers={"accept": "application/json"}
        )
        assert transport == MCPTransport.UNKNOWN


class TestEndpointExtraction:
    """Test SSE endpoint event extraction."""

    def test_extract_endpoint_url(self):
        """Test extracting endpoint URL from SSE data."""
        sse_data = 'event: endpoint\ndata: {"url": "http://localhost:8080/messages"}\n\n'
        url = extract_endpoint_from_sse(sse_data)
        assert url == "http://localhost:8080/messages"

    def test_extract_endpoint_url_with_crlf(self):
        """Test extracting endpoint URL with CRLF line endings."""
        sse_data = 'event: endpoint\r\ndata: {"url": "http://localhost:8080/messages"}\r\n\r\n'
        url = extract_endpoint_from_sse(sse_data)
        assert url == "http://localhost:8080/messages"

    def test_extract_endpoint_url_not_found(self):
        """Test when no endpoint event is present."""
        sse_data = 'event: message\ndata: {"jsonrpc": "2.0", "id": 1}\n\n'
        url = extract_endpoint_from_sse(sse_data)
        assert url is None

    def test_extract_endpoint_invalid_json(self):
        """Test when endpoint data is invalid JSON."""
        sse_data = 'event: endpoint\ndata: invalid json\n\n'
        url = extract_endpoint_from_sse(sse_data)
        assert url is None


class TestTransportTracker:
    """Test transport tracking across connections."""

    def test_update_and_get_transport(self):
        """Test updating and retrieving transport for a connection."""
        tracker = TransportTracker()

        # Update transport
        tracker.update_transport(
            "127.0.0.1", 12345, "127.0.0.1", 8080,
            MCPTransport.STREAMABLE_HTTP
        )

        # Should work in both directions
        assert tracker.get_transport("127.0.0.1", 12345, "127.0.0.1", 8080) == MCPTransport.STREAMABLE_HTTP
        assert tracker.get_transport("127.0.0.1", 8080, "127.0.0.1", 12345) == MCPTransport.STREAMABLE_HTTP

    def test_get_unknown_transport(self):
        """Test getting transport for unknown connection."""
        tracker = TransportTracker()
        assert tracker.get_transport("127.0.0.1", 12345, "127.0.0.1", 8080) == MCPTransport.UNKNOWN

    def test_store_endpoint_url(self):
        """Test storing endpoint URL for HTTP+SSE."""
        tracker = TransportTracker()

        tracker.store_endpoint_url(
            "127.0.0.1", 12345, "127.0.0.1", 8080,
            "http://localhost:8080/messages"
        )

        # Verify it was stored
        key = ("127.0.0.1", 12345, "127.0.0.1", 8080)
        assert tracker.endpoint_urls[key] == "http://localhost:8080/messages"

    def test_dont_update_unknown_transport(self):
        """Test that UNKNOWN transport doesn't overwrite existing."""
        tracker = TransportTracker()

        # Set a known transport
        tracker.update_transport(
            "127.0.0.1", 12345, "127.0.0.1", 8080,
            MCPTransport.STREAMABLE_HTTP
        )

        # Try to update with UNKNOWN (should not change)
        tracker.update_transport(
            "127.0.0.1", 12345, "127.0.0.1", 8080,
            MCPTransport.UNKNOWN
        )

        # Should still be STREAMABLE_HTTP
        assert tracker.get_transport("127.0.0.1", 12345, "127.0.0.1", 8080) == MCPTransport.STREAMABLE_HTTP
