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


def extract_server_info(message: str) -> Optional[dict[str, str]]:
    """
    Extract serverInfo from an initialize response.

    Returns dict with 'name' and 'version' if found, None otherwise.
    """
    parsed = parse_message(message)
    if not parsed:
        return None

    # Check if this is an initialize response
    if parsed.get("jsonrpc") == "2.0" and "result" in parsed:
        result = parsed.get("result", {})
        if isinstance(result, dict) and "serverInfo" in result:
            server_info = result["serverInfo"]
            if isinstance(server_info, dict) and "name" in server_info:
                return {
                    "name": server_info.get("name", "unknown"),
                    "version": server_info.get("version", "unknown")
                }

    return None


def extract_client_info(message: str) -> Optional[dict[str, str]]:
    """
    Extract clientInfo from an initialize request.

    Returns dict with 'name' and 'version' if found, None otherwise.
    """
    parsed = parse_message(message)
    if not parsed:
        return None

    # Check if this is an initialize request
    if (parsed.get("jsonrpc") == "2.0" and
        parsed.get("method") == "initialize" and
        "params" in parsed):
        params = parsed.get("params", {})
        if isinstance(params, dict) and "clientInfo" in params:
            client_info = params["clientInfo"]
            if isinstance(client_info, dict) and "name" in client_info:
                return {
                    "name": client_info.get("name", "unknown"),
                    "version": client_info.get("version", "unknown")
                }

    return None
