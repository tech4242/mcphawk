#!/usr/bin/env python3
"""TCP MCP client for testing."""

import json
import socket
import time


def send_mcp_message(sock, message):
    """Send a JSON-RPC message."""
    data = json.dumps(message).encode('utf-8')
    sock.sendall(data)
    print(f"Sent: {message.get('method', message.get('result', 'response'))}")

    # Read response if message has an ID
    if "id" in message:
        try:
            response = sock.recv(1024)
            if response:
                print("  Received response")
        except Exception:
            pass


def main():
    """Connect to TCP MCP server and send test messages."""
    print("Connecting to TCP MCP server on localhost:12345...")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(('localhost', 12345))
            print("Connected!")

            # Send initialize
            send_mcp_message(sock, {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                },
                "id": 1
            })
            time.sleep(0.5)

            # Send tools/list
            send_mcp_message(sock, {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 2
            })
            time.sleep(0.5)

            # Send a notification (no id)
            send_mcp_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": 50,
                    "operation": "processing"
                }
            })
            time.sleep(0.5)

            # Send tools/call
            send_mcp_message(sock, {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "calculator",
                    "arguments": {"a": 5, "b": 3}
                },
                "id": 3
            })
            time.sleep(0.5)

            # Send a batch of messages quickly
            print("\nSending batch of messages...")
            for i in range(4, 8):
                send_mcp_message(sock, {
                    "jsonrpc": "2.0",
                    "method": f"test/message_{i}",
                    "params": {"value": i * 10},
                    "id": i
                })
                time.sleep(0.1)

            print("\nAll messages sent!")
            # Keep connection open briefly to avoid reset
            time.sleep(2)

    except ConnectionRefusedError:
        print("Error: Could not connect to server. Make sure tcp_server.py is running.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

