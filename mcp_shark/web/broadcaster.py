"""
WebSocket broadcasting utility for MCP-Shark.

Broadcasts full log entries to all connected WebSocket clients.
"""

from typing import List, Dict, Any
from fastapi import WebSocket

active_clients: List[WebSocket] = []


async def broadcast_new_log(log_entry: Dict[str, Any]):
    """
    Broadcast a new log entry to all connected WebSocket clients.

    Args:
        log_entry: Dictionary representing the new log entry.
    """
    disconnected = []
    print(
        f"[DEBUG] Broadcasting to {len(active_clients)} clients: {log_entry}"
    )

    for ws in active_clients:
        try:
            await ws.send_json(log_entry)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        if ws in active_clients:
            active_clients.remove(ws)
