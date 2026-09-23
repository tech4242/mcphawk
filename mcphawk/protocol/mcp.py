"""MCP semantics on top of JSON-RPC, covering both protocol eras.

* **legacy**: 2024-11-05 through 2025-11-25, stateful ``initialize`` handshake.
* **modern**: 2026-07-28+, stateless; identity and version travel in ``_meta``.
"""

from typing import Any

LEGACY = "legacy"
MODERN = "modern"

MODERN_VERSIONS = ("2026-07-28",)
LEGACY_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
META_LOG_LEVEL = "io.modelcontextprotocol/logLevel"
META_SUBSCRIPTION_ID = "io.modelcontextprotocol/subscriptionId"

RESULT_COMPLETE = "complete"
RESULT_INPUT_REQUIRED = "input_required"

# Methods whose params carry a name that the 2026 transport mirrors into the
# ``Mcp-Name`` header; also what we show as the "target" of an exchange.
NAME_FIELDS = {
    "tools/call": "name",
    "prompts/get": "name",
    "resources/read": "uri",
    "resources/subscribe": "uri",
    "resources/unsubscribe": "uri",
}

# Results that must carry ttlMs/cacheScope from 2026-07-28 on.
CACHEABLE_METHODS = frozenset({
    "tools/list",
    "prompts/list",
    "resources/list",
    "resources/read",
    "resources/templates/list",
    "server/discover",
})

REMOVED_IN_MODERN = frozenset({
    "initialize",
    "notifications/initialized",
    "ping",
    "logging/setLevel",
    "notifications/roots/list_changed",
    "resources/subscribe",
    "resources/unsubscribe",
    "notifications/elicitation/complete",
    "tasks/result",
    "tasks/list",
})

# Server-to-client requests replaced by multi round-trip requests.
REPLACED_BY_MRTR = frozenset({
    "roots/list",
    "sampling/createMessage",
    "elicitation/create",
})

DEPRECATED_FEATURES = {
    "roots/list": "Roots",
    "notifications/roots/list_changed": "Roots",
    "sampling/createMessage": "Sampling",
    "logging/setLevel": "Logging",
    "notifications/message": "Logging",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _meta(container: Any) -> dict[str, Any]:
    return _dict(_dict(container).get("_meta"))


def _impl(value: Any) -> dict[str, str] | None:
    info = _dict(value)
    name = info.get("name")
    if not isinstance(name, str) or not name:
        return None
    version = info.get("version")
    return {"name": name, "version": str(version) if version is not None else ""}


def era_of_version(version: str | None) -> str | None:
    if not version:
        return None
    if version in MODERN_VERSIONS or version > LEGACY_VERSIONS[-1]:
        return MODERN
    return LEGACY


def target_of(msg: dict[str, Any]) -> str | None:
    """Tool name, prompt name or resource URI a request is about."""
    field = NAME_FIELDS.get(str(msg.get("method")))
    if not field:
        return None
    value = _dict(msg.get("params")).get(field)
    return str(value) if value is not None else None


def protocol_version(msg: dict[str, Any]) -> str | None:
    """Protocol version declared by a request, in either era."""
    params = _dict(msg.get("params"))
    modern = _meta(params).get(META_PROTOCOL_VERSION)
    if isinstance(modern, str):
        return modern
    if msg.get("method") == "initialize" and isinstance(params.get("protocolVersion"), str):
        return params["protocolVersion"]
    return None


def negotiated_version(msg: dict[str, Any]) -> str | None:
    """Version a server settled on in an ``initialize`` response."""
    version = _dict(msg.get("result")).get("protocolVersion")
    return version if isinstance(version, str) else None


def client_info(msg: dict[str, Any]) -> dict[str, str] | None:
    """Client identity from a request (``initialize`` or modern ``_meta``)."""
    params = _dict(msg.get("params"))
    modern = _impl(_meta(params).get(META_CLIENT_INFO))
    if modern:
        return modern
    if msg.get("method") == "initialize":
        return _impl(params.get("clientInfo"))
    return None


def server_info(msg: dict[str, Any], request_method: str | None = None) -> dict[str, str] | None:
    """Server identity from a response.

    Legacy servers identify themselves once in the ``initialize`` result;
    modern ones SHOULD stamp every result's ``_meta`` and MUST answer
    ``server/discover``.
    """
    result = _dict(msg.get("result"))
    modern = _impl(_meta(result).get(META_SERVER_INFO))
    if modern:
        return modern
    if request_method in ("initialize", "server/discover") or "serverInfo" in result:
        return _impl(result.get("serverInfo"))
    return None


def result_type(msg: dict[str, Any]) -> str:
    """``resultType`` of a response; absent means complete (spec §MRTR)."""
    value = _dict(msg.get("result")).get("resultType")
    return value if isinstance(value, str) else RESULT_COMPLETE


def request_state(msg: dict[str, Any]) -> str | None:
    """Opaque ``requestState`` from an input_required result or a retry."""
    for holder in (msg.get("result"), msg.get("params")):
        value = _dict(holder).get("requestState")
        if isinstance(value, str):
            return value
    return None


def input_requests(msg: dict[str, Any]) -> dict[str, Any]:
    return _dict(_dict(msg.get("result")).get("inputRequests"))


def is_tool_error(msg: dict[str, Any]) -> bool:
    """A ``tools/call`` that returned normally but reported ``isError``."""
    return bool(_dict(msg.get("result")).get("isError"))


def error_of(msg: dict[str, Any]) -> tuple[int | None, str | None]:
    error = _dict(msg.get("error"))
    code = error.get("code")
    message = error.get("message")
    return (
        code if isinstance(code, int) else None,
        str(message) if message is not None else None,
    )


def tool_error_text(msg: dict[str, Any]) -> str | None:
    """First text block of an ``isError`` tool result."""
    for block in _dict(msg.get("result")).get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text", ""))[:500]
    return None


def tools_from_list(msg: dict[str, Any]) -> list[dict[str, Any]]:
    tools = _dict(msg.get("result")).get("tools")
    return [t for t in tools if isinstance(t, dict)] if isinstance(tools, list) else []


def instructions_of(msg: dict[str, Any]) -> str | None:
    value = _dict(msg.get("result")).get("instructions")
    return value if isinstance(value, str) else None


def trace_parent(msg: dict[str, Any]) -> str | None:
    """W3C ``traceparent`` propagated in ``_meta`` (SEP-414)."""
    value = _meta(msg.get("params")).get("traceparent")
    return value if isinstance(value, str) else None
