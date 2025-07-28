"""Utility functions for MCPHawk."""

import json
from typing import Any, Optional


def parse_message(message: str) -> Optional[dict[str, Any]]:
    """Parse a JSON message string."""
    try:
        if isinstance(message, str):
            return json.loads(message)
        return message
    except (json.JSONDecodeError, TypeError):
        return None


def get_message_type(message: str) -> str:
    """
    Determine the type of a JSON-RPC message.

    Returns: 'request', 'response', 'notification', 'error', or 'unknown'
    """
    parsed = parse_message(message)
    if not parsed:
        return "unknown"

    # Check if it's a valid JSON-RPC 2.0 message
    if parsed.get("jsonrpc") != "2.0":
        return "unknown"

    # Error response (has error and id)
    if "error" in parsed and "id" in parsed:
        return "error"

    # Response (has result and id)
    if "result" in parsed and "id" in parsed:
        return "response"

    # Request (has method and id)
    if "method" in parsed and "id" in parsed:
        return "request"

    # Notification (has method but no id)
    if "method" in parsed and "id" not in parsed:
        return "notification"

    return "unknown"


def get_method_name(message: str) -> Optional[str]:
    """Extract method name from a JSON-RPC message."""
    parsed = parse_message(message)
    return parsed.get("method") if parsed else None
