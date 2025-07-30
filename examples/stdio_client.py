#!/usr/bin/env python3
"""
Example stdio client for MCPHawk MCP server.

This demonstrates how to communicate with MCPHawk's MCP server using the stdio transport.
The MCP protocol requires:
1. Initialize request
2. Initialized notification
3. Then you can make tool calls
"""

import json
import queue
import subprocess
import threading
from typing import Any, Optional


class MCPHawkStdioClient:
    """Client for communicating with MCPHawk MCP server over stdio."""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.proc = None
        self.stderr_queue = queue.Queue()
        self.request_id = 0

    def connect(self) -> bool:
        """Start the MCP server process and initialize connection."""
        try:
            # Start the MCP server
            self.proc = subprocess.Popen(
                ["mcphawk", "mcp", "--transport", "stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0  # Unbuffered
            )

            # Start stderr reader thread
            self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self.stderr_thread.start()

            # Send initialize request
            init_response = self._send_request({
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcphawk-stdio-client", "version": "1.0"}
                }
            })

            if not init_response or "error" in init_response:
                print(f"Failed to initialize: {init_response}")
                return False

            # Send initialized notification
            self._send_notification({
                "method": "notifications/initialized",
                "params": {}
            })

            if self.debug:
                print(f"Connected to server: {init_response['result']['serverInfo']}")

            return True

        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    def _read_stderr(self):
        """Read stderr in a separate thread."""
        while self.proc and self.proc.poll() is None:
            line = self.proc.stderr.readline()
            if line:
                self.stderr_queue.put(line.strip())

    def _send_request(self, request: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        self.request_id += 1
        request["jsonrpc"] = "2.0"
        request["id"] = self.request_id

        request_str = json.dumps(request)
        if self.debug:
            print(f">>> {request_str}")

        self.proc.stdin.write(request_str + "\n")
        self.proc.stdin.flush()

        # Read response
        response_line = self.proc.stdout.readline()
        if response_line:
            try:
                response = json.loads(response_line)
                if self.debug:
                    print(f"<<< {json.dumps(response, indent=2)}")
                return response
            except json.JSONDecodeError as e:
                print(f"Failed to decode response: {e}")
                print(f"Raw: {response_line}")
                return None
        return None

    def _send_notification(self, notification: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification["jsonrpc"] = "2.0"

        notification_str = json.dumps(notification)
        if self.debug:
            print(f">>> {notification_str}")

        self.proc.stdin.write(notification_str + "\n")
        self.proc.stdin.flush()

    def list_tools(self) -> Optional[list]:
        """Get list of available tools."""
        response = self._send_request({
            "method": "tools/list",
            "params": {}
        })

        if response and "result" in response:
            return response["result"]["tools"]
        return None

    def call_tool(self, tool_name: str, arguments: Optional[dict[str, Any]] = None) -> Optional[Any]:
        """Call a tool with given arguments."""
        response = self._send_request({
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        })

        if response and "result" in response:
            # Extract the text content from the response
            content = response["result"]["content"]
            if content and len(content) > 0:
                text = content[0]["text"]
                try:
                    # Try to parse as JSON
                    return json.loads(text)
                except json.JSONDecodeError:
                    # Return as plain text if not JSON
                    return text
        return None

    def close(self):
        """Close the connection."""
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
            self.proc = None


def main():
    """Example usage of the MCPHawk stdio client."""
    client = MCPHawkStdioClient(debug=True)

    print("Connecting to MCPHawk MCP server...")
    if not client.connect():
        print("Failed to connect!")
        return

    print("\n1. Listing available tools:")
    tools = client.list_tools()
    if tools:
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

    print("\n2. Getting traffic statistics:")
    stats = client.call_tool("get_stats")
    if stats:
        print(f"  Total logs: {stats['total']}")
        print(f"  Requests: {stats['requests']}")
        print(f"  Responses: {stats['responses']}")
        print(f"  Notifications: {stats['notifications']}")
        print(f"  Errors: {stats['errors']}")

    print("\n3. Querying recent traffic:")
    logs = client.call_tool("query_traffic", {"limit": 5})
    if logs:
        print(f"  Found {len(logs)} recent log entries")
        for log in logs:
            msg_preview = log['message'][:50] + "..." if len(log['message']) > 50 else log['message']
            print(f"  - {log['timestamp']}: {msg_preview}")

    print("\n4. Listing captured methods:")
    methods = client.call_tool("list_methods")
    if methods:
        print(f"  Found {len(methods)} unique methods:")
        for method in methods[:10]:  # Show first 10
            print(f"  - {method}")
        if len(methods) > 10:
            print(f"  ... and {len(methods) - 10} more")

    print("\nClosing connection...")
    client.close()


if __name__ == "__main__":
    main()
