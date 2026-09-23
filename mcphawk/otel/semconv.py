"""Mapping captured MCP traffic onto the OpenTelemetry MCP semantic conventions.

https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md
(status: development). Names defined there are used verbatim; everything
MCPHawk adds lives under ``mcphawk.*``. Pure functions only, so this module
works without the OpenTelemetry SDK installed.
"""

import hashlib
import json
import re
from typing import Any

from mcphawk import links
from mcphawk.protocol import mcp as proto
from mcphawk.runs import client_label as _run_client_label

# Advisory boundaries for mcp.*.operation.duration, in seconds (semconv).
DURATION_BUCKETS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60, 120, 300)

OPERATION_DURATION = "mcp.client.operation.duration"
RESULT_TOKENS = "mcphawk.tool.result.tokens"
DEFINITION_TOKENS = "mcphawk.tool.definition.tokens"

MAX_LOG_PAYLOAD = 16_000

_TRACEPARENT = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def _hash_id(text: str, bits: int) -> int:
    value = int.from_bytes(hashlib.sha256(text.encode()).digest()[: bits // 8], "big")
    return value or 1  # all-zero ids are invalid in OTel


def run_trace_id(run_key: str) -> int:
    return _hash_id(f"run:{run_key}", 128)


def run_span_id(run_key: str) -> int:
    return _hash_id(f"run-root:{run_key}", 64)


def exchange_span_id(exchange_id: int) -> int:
    return _hash_id(f"exchange:{exchange_id}", 64)


def session_trace_id(session_id: str) -> int:
    """Fallback trace for calls that belong to no run (should not happen)."""
    return _hash_id(f"session:{session_id}", 128)


def parse_traceparent(value: Any) -> tuple[int, int, int] | None:
    """(trace_id, span_id, flags) from a W3C ``traceparent``, or None."""
    if not isinstance(value, str):
        return None
    match = _TRACEPARENT.match(value.strip().lower())
    if not match:
        return None
    trace_id, span_id, flags = (int(g, 16) for g in match.groups())
    if not trace_id or not span_id:
        return None
    return trace_id, span_id, flags


def request_traceparent(request_body: Any) -> tuple[int, int, int] | None:
    if not isinstance(request_body, dict):
        return None
    return parse_traceparent(proto.trace_parent(request_body))


def span_name(exchange: dict[str, Any]) -> str:
    """``{mcp.method.name} {target}`` as the conventions prescribe."""
    if exchange.get("target") and exchange["method"] in ("tools/call", "prompts/get"):
        return f"{exchange['method']} {exchange['target']}"
    return exchange["method"]


def error_type(exchange: dict[str, Any]) -> str | None:
    status = exchange["status"]
    if status == "tool_error":
        return "tool_error"
    if status == "error":
        code = exchange.get("error_code")
        return str(code) if code is not None else "error"
    if status in ("cancelled", "abandoned", "hung"):
        return status
    return None


def client_label(session: dict[str, Any]) -> str:
    return _run_client_label([session], session.get("client_key") or "")


def _target_attributes(exchange: dict[str, Any]) -> dict[str, Any]:
    method, target = exchange["method"], exchange.get("target")
    if not target:
        return {}
    if method == "tools/call":
        return {"gen_ai.tool.name": target, "gen_ai.operation.name": "execute_tool"}
    if method == "prompts/get":
        return {"gen_ai.prompt.name": target}
    if method.startswith("resources/"):
        return {"mcp.resource.uri": target}
    return {}


def _network_attributes(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("transport") == "stdio":
        return {"network.transport": "pipe"}
    attributes: dict[str, Any] = {"network.transport": "tcp", "network.protocol.name": "http"}
    target = session.get("target") or ""
    match = re.match(r"^\w+://(\[[^\]]+\]|[^:/]+)(?::(\d+))?", target)
    if match:
        attributes["server.address"] = match.group(1).strip("[]")
        if match.group(2):
            attributes["server.port"] = int(match.group(2))
    return attributes


def metric_attributes(exchange: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """Low-cardinality attributes shared by metrics (no ids, no URIs)."""
    attributes: dict[str, Any] = {
        "mcp.method.name": exchange["method"],
        "mcphawk.server.name": session.get("display_name") or "unknown",
        "mcphawk.client.name": client_label(session),
    }
    if exchange["method"] == "tools/call" and exchange.get("target"):
        attributes["gen_ai.tool.name"] = exchange["target"]
    if session.get("protocol_version"):
        attributes["mcp.protocol.version"] = session["protocol_version"]
    failure = error_type(exchange)
    if failure:
        attributes["error.type"] = failure
    return attributes


def span_attributes(exchange: dict[str, Any], session: dict[str, Any],
                    run_key: str | None) -> dict[str, Any]:
    attributes = metric_attributes(exchange, session)
    attributes.update(_target_attributes(exchange))
    attributes.update(_network_attributes(session))
    if exchange.get("rpc_id") is not None:
        attributes["jsonrpc.request.id"] = str(json.loads(exchange["rpc_id"]))
    if exchange.get("error_code") is not None:
        attributes["rpc.response.status_code"] = str(exchange["error_code"])
    attributes.update({
        "mcphawk.session.id": exchange["session_id"],
        "mcphawk.exchange.id": exchange["id"],
        "mcphawk.exchange.url": links.exchange_url(exchange["id"]),
        "mcphawk.initiator": exchange["initiator"],
        "mcphawk.request.tokens": exchange.get("request_tokens") or 0,
        "mcphawk.result.tokens": exchange.get("response_tokens") or 0,
    })
    if exchange["status"] == "input_required":
        attributes["mcphawk.result.type"] = "input_required"
    if run_key:
        attributes["mcphawk.run.key"] = run_key
    return attributes


def log_fields(message: dict[str, Any], session: dict[str, Any],
               include_payload: bool) -> tuple[str, str, dict[str, Any]]:
    """(severity, body, attributes) for one captured message."""
    method = message.get("method")
    direction = "client to server" if message["direction"] == "c2s" else "server to client"
    what = method or (f"response to id {json.loads(message['rpc_id'])}"
                      if message.get("rpc_id") else message["kind"])
    body = f"{message['kind']} {what} ({direction})"
    severity = "INFO"
    attributes: dict[str, Any] = {
        "mcphawk.message.id": message["id"],
        "mcphawk.message.kind": message["kind"],
        "mcphawk.direction": message["direction"],
        "mcphawk.session.id": message["session_id"],
        "mcphawk.server.name": session.get("display_name") or "unknown",
        "mcphawk.client.name": client_label(session),
        "mcphawk.message.bytes": message.get("size") or 0,
    }
    if method:
        attributes["mcp.method.name"] = method
    if message.get("rpc_id"):
        attributes["jsonrpc.request.id"] = str(json.loads(message["rpc_id"]))
    content = message.get("body")
    if message["kind"] == "error" and isinstance(content, dict):
        code, text = proto.error_of(content)
        severity = "ERROR"
        attributes["error.type"] = str(code) if code is not None else "error"
        body += f": {text}" if text else ""
    elif message["kind"] == "response" and isinstance(content, dict) and proto.is_tool_error(
            content):
        severity = "ERROR"
        attributes["error.type"] = "tool_error"
        text = proto.tool_error_text(content)
        body += f": {text}" if text else ""
    elif message["kind"] == "invalid":
        severity = "WARN"
        body += f": {message.get('note') or 'not valid JSON-RPC'}"
    if include_payload:
        payload = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        attributes["mcphawk.message.payload"] = payload[:MAX_LOG_PAYLOAD]
    return severity, body, attributes
