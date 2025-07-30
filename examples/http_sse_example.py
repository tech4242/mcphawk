#!/usr/bin/env python3
"""
Proper HTTP+SSE MCP client traffic generator.

This simulates the legacy HTTP+SSE transport pattern as documented:
1. GET request to /sse endpoint to establish SSE connection
2. Server sends "endpoint" event with the message endpoint URL
3. Client POSTs JSON-RPC messages to the message endpoint

This example creates traffic that MCPHawk can properly detect as HTTP+SSE.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests


class MockHTTPSSEServer(BaseHTTPRequestHandler):
    """Mock server that implements HTTP+SSE pattern."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET request for SSE connection."""
        if self.path == '/sse':
            print("[Mock Server] Received GET /sse - sending SSE response")
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            # Send the endpoint event as per HTTP+SSE spec
            endpoint_event = 'event: endpoint\ndata: {"url": "/messages"}\n\n'
            self.wfile.write(endpoint_event.encode())
            self.wfile.flush()

            # For this example, close after sending endpoint
            # Real servers would keep the connection open for streaming
            return
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST request to message endpoint."""
        if self.path == '/messages':
            print("[Mock Server] Received POST /messages")
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            # Parse the JSON-RPC request
            try:
                request = json.loads(post_data)
                print(f"[Mock Server] Request: {request}")

                # Send a simple response
                response = {
                    "jsonrpc": "2.0",
                    "result": {"initialized": True},
                    "id": request.get("id")
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                print(f"[Mock Server] Error: {e}")
                self.send_error(400)
        else:
            self.send_error(404)


def run_mock_server(port=8766):
    """Run the mock HTTP+SSE server in a thread."""
    server = HTTPServer(('localhost', port), MockHTTPSSEServer)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server


def simulate_http_sse_client(server_port=8766):
    """Simulate HTTP+SSE client traffic pattern."""

    print("\nSimulating HTTP+SSE MCP Client (Legacy Pattern)")
    print("=" * 50)

    server_url = f"http://localhost:{server_port}"

    # Step 1: Establish SSE connection with GET request
    print("\n1. Establishing SSE connection...")
    print(f"   GET {server_url}/sse")
    print("   Accept: text/event-stream")

    # Use requests library for better control
    session = requests.Session()

    endpoint_url = None

    try:
        # Make GET request with SSE accept header
        headers = {'Accept': 'text/event-stream'}
        response = session.get(f"{server_url}/sse", headers=headers, stream=True, timeout=2)

        print(f"   Response: {response.status_code} {response.reason}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")

        # Read the endpoint event with timeout on iter_lines
        try:
            for line in response.iter_lines(decode_unicode=True, chunk_size=1):
                if line:
                    print(f"   SSE: {line}")
                    if line.startswith('data:'):
                        data = json.loads(line[5:].strip())
                        endpoint_url = data.get('url')
                        break
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            print("   SSE connection closed/timed out (expected)")

        response.close()  # Close the streaming connection

    except Exception as e:
        print(f"   Error during GET: {e}")

    # Always try the POST request, even if GET had issues
    if not endpoint_url:
        endpoint_url = "/messages"  # Default endpoint for HTTP+SSE
        print(f"\n2. Using default endpoint URL: {endpoint_url}")
    else:
        print(f"\n2. Server sent endpoint URL: {endpoint_url}")

    # Step 2: Send JSON-RPC request to the endpoint
    print("\n3. Sending JSON-RPC request to endpoint...")
    print(f"   POST {server_url}{endpoint_url}")
    print("   Content-Type: application/json")

    try:
        # Send initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "http-sse-test",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }

        # Important: No Accept header with dual types for HTTP+SSE POST
        post_response = session.post(
            f"{server_url}{endpoint_url}",
            json=initialize_request,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )

        print(f"   Response: {post_response.status_code}")
        if post_response.status_code == 200:
            print(f"   Result: {post_response.json()}")

    except Exception as e:
        print(f"   Error during POST: {e}")

    print("\n" + "=" * 50)
    print("HTTP+SSE pattern demonstration complete")
    print("Check MCPHawk to see the detected transport type:")
    print("- GET /sse with Accept: text/event-stream → HTTP+SSE")
    print("- Server sends 'endpoint' event → Confirms HTTP+SSE")
    print("- POST to endpoint without dual Accept → HTTP+SSE pattern")


if __name__ == "__main__":
    print("HTTP+SSE MCP Client Example (Proper Implementation)")
    print("This demonstrates the legacy HTTP+SSE transport pattern")
    print("with a mock server that properly implements the protocol\n")

    # Start mock server
    port = 8766
    print(f"Starting mock HTTP+SSE server on port {port}...")
    server = run_mock_server(port)
    time.sleep(1)  # Give server time to start

    # Run client simulation
    simulate_http_sse_client(port)

    # Keep server running briefly for any remaining packets
    time.sleep(1)
    print("\nDone!")
