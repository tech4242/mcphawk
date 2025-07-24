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
    if not active_clients:
        return
        
    disconnected = []
    # Only show client count, not the full log entry
    print(f"[DEBUG] Broadcasting to {len(active_clients)} clients")

    for ws in active_clients:
        try:
            await ws.send_json(log_entry)
        except Exception as e:
            print(f"[DEBUG] Failed to send to client: {type(e).__name__}")
            disconnected.append(ws)

    # Clean up disconnected clients
    if disconnected:
        for ws in disconnected:
            if ws in active_clients:
                active_clients.remove(ws)
        print(f"[DEBUG] Removed {len(disconnected)} disconnected clients, {len(active_clients)} remaining")
