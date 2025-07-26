#!/usr/bin/env python3
"""WebSocket MCP client for testing."""

import asyncio
import json
import logging

import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_mcp_message(websocket, message):
    """Send a JSON-RPC message and optionally wait for response."""
    await websocket.send(json.dumps(message))
    method = message.get('method', message.get('result', 'response'))
    logger.info(f"Sent: {method}")

    # If it has an ID, wait for response
    if "id" in message:
        response = await websocket.recv()
        response_data = json.loads(response)
        logger.info(f"Received response: {response_data.get('result', response_data.get('error'))}")
        return response_data


async def main():
    """Connect to WebSocket MCP server and send test messages."""
    uri = "ws://localhost:8765"
    logger.info(f"Connecting to WebSocket MCP server at {uri}...")

    try:
        async with websockets.connect(uri, compression=None) as websocket:
            logger.info("Connected!")

            # Send initialize
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                },
                "id": 1
            })

            # Send tools/list
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 2
            })

            # Send a notification (no id, no response expected)
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "notifications/progress",
                "params": {
                    "progress": 50,
                    "operation": "processing"
                }
            })
            await asyncio.sleep(0.5)  # Small delay after notification

            # Send tools/call
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "calculator",
                    "arguments": {"a": 5, "b": 3}
                },
                "id": 3
            })

            # Send a large message to test extended length
            large_data = "x" * 1000
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "test/large_message",
                "params": {"data": large_data},
                "id": 4
            })

            # Send a batch of messages quickly
            logger.info("\nSending batch of messages...")
            tasks = []
            for i in range(5, 10):
                message = {
                    "jsonrpc": "2.0",
                    "method": f"test/message_{i}",
                    "params": {"value": i * 10},
                    "id": i
                }
                tasks.append(send_mcp_message(websocket, message))

            # Wait for all responses
            await asyncio.gather(*tasks)

            # Send one more notification before closing
            await send_mcp_message(websocket, {
                "jsonrpc": "2.0",
                "method": "notifications/closing",
                "params": {"reason": "test complete"}
            })

            logger.info("\nAll messages sent!")
            await asyncio.sleep(0.5)

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
    except ConnectionRefusedError:
        logger.error("Could not connect to server. Make sure ws_server.py is running.")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

