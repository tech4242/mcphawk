"""Rough token estimates.

MCPHawk does not bundle a tokenizer; ~4 characters per token is close enough
for comparing tools against each other and is always labelled as an estimate.
"""

import json
from typing import Any

CHARS_PER_TOKEN = 4
# Flat estimate for a base64 image block; providers bill images by pixels, not
# by payload length, so the raw base64 size would wildly overstate the cost.
IMAGE_TOKENS = 1500


def estimate_text(text: str) -> int:
    if not text:
        return 0
    return max(1, -(-len(text) // CHARS_PER_TOKEN))


def estimate_json(value: Any) -> int:
    if value is None:
        return 0
    return estimate_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def estimate_content(blocks: Any) -> int:
    """Estimate tokens for MCP content blocks as a model would see them."""
    if not isinstance(blocks, list):
        return estimate_json(blocks)
    total = 0
    for block in blocks:
        if not isinstance(block, dict):
            total += estimate_json(block)
            continue
        kind = block.get("type")
        if kind == "text":
            total += estimate_text(str(block.get("text", "")))
        elif kind in ("image", "audio"):
            total += IMAGE_TOKENS
        elif kind == "resource":
            resource = block.get("resource") or {}
            if isinstance(resource, dict) and "text" in resource:
                total += estimate_text(str(resource["text"]))
            else:
                total += IMAGE_TOKENS
        else:
            total += estimate_json(block)
    return total
