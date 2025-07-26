#!/usr/bin/env python3
"""WebSocket MCP server for testing."""

import asyncio
import json
import logging

import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_mcp_message(websocket, message):
    """Handle incoming MCP message and send response."""
    try:
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id")

        logger.info(f"Received: {method} (id: {msg_id})")

        # Only respond to requests (with id), not notifications
        if msg_id is None:
            logger.info(f"Notification received: {method}")
            return

        # Generate response based on method
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True}
                    },
                    "serverInfo": {
                        "name": "test-ws-server",
                        "version": "1.0.0"
                    }
                },
                "id": msg_id
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {
                            "name": "calculator",
                            "description": "Perform calculations",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "a": {"type": "number"},
                                    "b": {"type": "number"}
                                }
                            }
                        },
                        {
                            "name": "echo",
                            "description": "Echo back input",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string"}
                                }
                            }
                        }
                    ]
                },
                "id": msg_id
            }
        elif method == "tools/call":
            params = data.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name == "calculator":
                result = args.get("a", 0) + args.get("b", 0)
                response = {
                    "jsonrpc": "2.0",
                    "result": {"value": result},
                    "id": msg_id
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "result": {"echo": str(args)},
                    "id": msg_id
                }
        else:
            # Generic response
            response = {
                "jsonrpc": "2.0",
                "result": {"status": "ok", "method": method},
                "id": msg_id
            }

        await websocket.send(json.dumps(response))
        logger.info(f"Sent response for {method}")

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON: {message}")
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if msg_id:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                },
                "id": msg_id
            }
            await websocket.send(json.dumps(error_response))


async def mcp_server(websocket):
    """Handle WebSocket connection."""
    logger.info("Client connected")

    try:
        async for message in websocket:
            await handle_mcp_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Connection error: {e}")


async def main():
    """Start WebSocket MCP server."""
    port = 8765
    logger.info(f"Starting WebSocket MCP server on ws://localhost:{port}")

    async with websockets.serve(mcp_server, "localhost", port, compression=None):
        logger.info("Server ready. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")

