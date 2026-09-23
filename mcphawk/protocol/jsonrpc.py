"""JSON-RPC 2.0 framing helpers."""

import json
from typing import Any

REQUEST = "request"
NOTIFICATION = "notification"
RESPONSE = "response"
ERROR = "error"
INVALID = "invalid"


def parse_frame(text: str) -> list[dict[str, Any]] | None:
    """Parse one wire frame into a list of JSON-RPC messages.

    Returns ``None`` when the frame is not JSON at all, and a list (one entry
    per message, batches flattened) otherwise. Non-object batch members are
    kept as ``{}`` so they surface as invalid rather than disappearing.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, list):
        return [m if isinstance(m, dict) else {} for m in data]
    if isinstance(data, dict):
        return [data]
    return None


def classify(msg: dict[str, Any]) -> str:
    """Classify a single JSON-RPC message."""
    if msg.get("jsonrpc") != "2.0":
        return INVALID
    has_id = "id" in msg and msg["id"] is not None
    if isinstance(msg.get("method"), str):
        return REQUEST if has_id else NOTIFICATION
    if "error" in msg and isinstance(msg["error"], dict):
        return ERROR
    if "result" in msg and has_id:
        return RESPONSE
    return INVALID


def id_key(rpc_id: Any) -> str | None:
    """Stable string form of a JSON-RPC id (``1`` and ``"1"`` stay distinct)."""
    if rpc_id is None:
        return None
    return json.dumps(rpc_id, sort_keys=True)
