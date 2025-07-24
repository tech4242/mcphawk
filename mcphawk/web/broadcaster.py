import logging
from typing import Any

from fastapi import WebSocket

# Set up logger for this module
logger = logging.getLogger(__name__)

active_clients: list[WebSocket] = []


async def broadcast_new_log(log_entry: dict[str, Any]):
    """
    Broadcast a new log entry to all connected WebSocket clients.

    Args:
        log_entry: Dictionary representing the new log entry.
    """
    if not active_clients:
        return

    disconnected = []
    # Only show client count, not the full log entry
    logger.debug(f"Broadcasting to {len(active_clients)} clients")

    for ws in active_clients:
        try:
            await ws.send_json(log_entry)
        except Exception as e:
            logger.debug(f"Failed to send to client: {type(e).__name__}")
            disconnected.append(ws)

    # Clean up disconnected clients
    if disconnected:
        for ws in disconnected:
            if ws in active_clients:
                active_clients.remove(ws)
        logger.debug(f"Removed {len(disconnected)} disconnected clients, {len(active_clients)} remaining")
