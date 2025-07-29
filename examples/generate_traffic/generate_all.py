#!/usr/bin/env python3
"""Generate TCP MCP traffic for testing MCPHawk."""

import asyncio
import contextlib
import json
import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def run_tcp_server():
    """Run the TCP server in a subprocess."""
    script_path = Path(__file__).parent / "tcp_server.py"
    return subprocess.Popen([sys.executable, str(script_path)])



def send_tcp_traffic():
    """Send TCP MCP traffic."""
    logger.info("Sending TCP traffic...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 12345))

        messages = [
            {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05"}, "id": 1},
            {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            {"jsonrpc": "2.0", "method": "notifications/tcp_test", "params": {"source": "tcp"}},
            {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "test_tool", "arguments": {}}, "id": 3},
        ]

        for msg in messages:
            data = json.dumps(msg).encode('utf-8')
            sock.sendall(data)
            logger.info(f"  TCP sent: {msg.get('method')}")

            # Read response if it has an ID
            if "id" in msg:
                try:
                    response = sock.recv(1024)
                    if response:
                        logger.info("  TCP received response")
                except Exception:
                    pass

            time.sleep(0.2)

        # Keep connection open a bit longer
        time.sleep(1)
        sock.close()

    except Exception as e:
        logger.error(f"TCP client error: {e}")



def check_port(port):
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result != 0


async def main():
    """Generate all traffic types."""
    logger.info("MCPHawk Traffic Generator")
    logger.info("========================\n")

    # Check if ports are available
    if not check_port(12345):
        logger.error("Port 12345 is already in use. Please stop the existing TCP server.")
        return

    logger.info("Starting server...")

    # Start server
    tcp_server = run_tcp_server()

    # Give server time to start
    logger.info("Waiting for server to start...")
    await asyncio.sleep(2)

    try:
        # Send TCP traffic
        send_tcp_traffic()

        logger.info("\n✅ All traffic sent successfully!")
        logger.info("\nServer will continue running. Press Ctrl+C to stop.")

        # Keep running
        await asyncio.Future()

    except KeyboardInterrupt:
        logger.info("\nStopping server...")
    finally:
        # Clean up
        tcp_server.terminate()
        tcp_server.wait()
        logger.info("Server stopped.")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

