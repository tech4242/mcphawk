#!/usr/bin/env python3
"""
Test script to generate different MCP/JSON-RPC message patterns
to test the new UI's message type detection.
"""

import socket
import json
import time
import sys

def send_message(sock, message):
    """Send a JSON-RPC message over the socket."""
    json_str = json.dumps(message)
    print(f"Sending: {json_str}")
    sock.sendall(json_str.encode() + b'\n')
    time.sleep(0.5)  # Small delay to make messages easier to follow

def main():
    host = '127.0.0.1'
    port = 12345
    
    print(f"Connecting to {host}:{port}...")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
            print("Connected! Sending test messages...\n")
            
            # 1. Request-Response pattern
            print("=== Test 1: Request-Response Pattern ===")
            # Request
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            })
            # Response
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "calculator", "description": "Basic math operations"},
                        {"name": "weather", "description": "Get weather information"}
                    ]
                }
            })
            
            # 2. Notification pattern (no response expected)
            print("\n=== Test 2: Notification Pattern ===")
            send_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": 0.25,
                    "message": "Processing started..."
                }
            })
            send_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": 0.50,
                    "message": "Halfway complete..."
                }
            })
            send_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": 1.0,
                    "message": "Processing complete!"
                }
            })
            
            # 3. Error response pattern
            print("\n=== Test 3: Error Response Pattern ===")
            # Request
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "nonexistent_tool"
                }
            })
            # Error response
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {
                    "code": -32601,
                    "message": "Tool not found",
                    "data": {"tool": "nonexistent_tool"}
                }
            })
            
            # 4. Multiple requests before responses (async pattern)
            print("\n=== Test 4: Async Pattern - Multiple Requests ===")
            # Send multiple requests
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": "file:///data1.txt"}
            })
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {"uri": "file:///data2.txt"}
            })
            # Responses arrive out of order
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 4,
                "result": {"contents": "Data from file 2"}
            })
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 3,
                "result": {"contents": "Data from file 1"}
            })
            
            # 5. Server-initiated request pattern
            print("\n=== Test 5: Server-Initiated Request ===")
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": "server-1",
                "method": "sampling/createMessage",
                "params": {
                    "messages": [
                        {"role": "user", "content": "What's the weather?"}
                    ],
                    "maxTokens": 100
                }
            })
            
            # 6. Mixed patterns with progress notifications
            print("\n=== Test 6: Mixed Pattern - Request with Progress ===")
            # Initial request
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "long_running_task",
                    "arguments": {"duration": 5}
                }
            })
            # Progress notifications (no ID)
            send_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {"taskId": 5, "progress": 0.33}
            })
            send_message(sock, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {"taskId": 5, "progress": 0.66}
            })
            # Final response
            send_message(sock, {
                "jsonrpc": "2.0",
                "id": 5,
                "result": {"status": "completed", "output": "Task finished!"}
            })
            
            print("\n=== All test messages sent! ===")
            print("Check the MCPHawk UI to see how messages are displayed.")
            
    except ConnectionRefusedError:
        print(f"Error: Could not connect to {host}:{port}")
        print("Make sure the dummy MCP server is running:")
        print("  python3 dummy_mcp_server.py")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()