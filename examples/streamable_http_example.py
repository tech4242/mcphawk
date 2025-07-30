#!/usr/bin/env python3
"""
Example Streamable HTTP MCP client traffic generator.

This demonstrates the Streamable HTTP transport pattern for testing MCPHawk's transport detection.
Streamable HTTP uses:
1. POST request with dual Accept headers (application/json, text/event-stream)
2. Server can respond with either JSON or SSE
"""

import json
import urllib.error
import urllib.request


def simulate_streamable_http_client():
    """Simulate Streamable HTTP client traffic pattern."""

    print("Simulating Streamable HTTP MCP Client")
    print("=" * 50)

    server_url = "http://localhost:8765"

    print("\n1. Sending request with dual Accept headers (Streamable HTTP pattern)...")
    print(f"   POST {server_url}/mcp")
    print("   Accept: application/json, text/event-stream")
    print("   Content-Type: application/json")

    # Send a sample initialize request
    initialize_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",  # New protocol version
            "capabilities": {},
            "clientInfo": {
                "name": "streamable-http-test",
                "version": "1.0.0"
            }
        },
        "id": 1
    }

    try:
        data = json.dumps(initialize_request).encode('utf-8')
        req = urllib.request.Request(
            f"{server_url}/mcp",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"  # Key difference!
            }
        )

        print(f"\n   Request body: {json.dumps(initialize_request, indent=2)}")

        with urllib.request.urlopen(req) as response:
            print(f"\n   Response: {response.status}")
            content_type = response.headers.get('Content-Type', '')
            print(f"   Content-Type: {content_type}")

            if 'text/event-stream' in content_type:
                print("   Server returned SSE response (streaming)")
            else:
                print("   Server returned JSON response")

    except urllib.error.URLError as e:
        print(f"   Connection failed: {e}")

    # Send another request that might get a different response type
    print("\n2. Sending tool call request...")
    print(f"   POST {server_url}/mcp")
    print("   Accept: application/json, text/event-stream")

    tool_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "long_running_tool",
            "arguments": {}
        },
        "id": 2
    }

    try:
        data = json.dumps(tool_request).encode('utf-8')
        req = urllib.request.Request(
            f"{server_url}/mcp",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )

        with urllib.request.urlopen(req) as response:
            print(f"\n   Response: {response.status}")
            content_type = response.headers.get('Content-Type', '')
            print(f"   Content-Type: {content_type}")

    except urllib.error.URLError as e:
        print(f"   Connection failed: {e}")

    print("\n" + "=" * 50)
    print("Streamable HTTP pattern demonstration complete")
    print("Check MCPHawk to see how it detected the transport type:")
    print("- POST with Accept: application/json, text/event-stream → Streamable HTTP")


if __name__ == "__main__":
    print("Streamable HTTP MCP Client Example")
    print("This demonstrates the Streamable HTTP transport pattern")
    print("This should work with our MCP server\n")

    simulate_streamable_http_client()
