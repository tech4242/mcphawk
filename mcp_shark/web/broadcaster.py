"""
WebSocket broadcasting utility for MCP-Shark.

Keeps track of active WebSocket clients and provides a function
to broadcast new log entries to all connected clients.
"""

from typing import List
from fastapi import WebSocket

active_clients: List[WebSocket] = []


async def broadcast_new_log(log_entry: dict):
    """
    Broadcast a new log entry to all connected WebSocket clients.

    Args:
        log_entry: Dictionary representing the new log entry.
    """
    disconnected = []

    for ws in active_clients:
        try:
            await ws.send_json(log_entry)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        if ws in active_clients:
            active_clients.remove(ws)
