"""Spec conformance checks for captured sessions.

Rules are keyed to the protocol era a session negotiated: a 2025 server is
not faulted for lacking ``resultType``, but a 2026-07-28 one is.
"""

from collections import OrderedDict
from typing import Any

from mcphawk.protocol import jsonrpc
from mcphawk.protocol import mcp as proto
from mcphawk.query import Query

ERROR = "error"
WARNING = "warning"
INFO = "info"

SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

RULES: dict[str, tuple[str, str]] = {
    "non-json-output": (ERROR, "Non-JSON output on the protocol stream"),
    "invalid-jsonrpc": (ERROR, "Message is not valid JSON-RPC 2.0"),
    "unmatched-response": (WARNING, "Response without a matching request"),
    "missing-result-type": (ERROR, "Result is missing required resultType"),
    "missing-cache-hints": (ERROR, "Cacheable result is missing ttlMs/cacheScope"),
    "removed-method": (ERROR, "Method was removed in 2026-07-28"),
    "server-initiated-request": (ERROR, "Server-initiated request; use multi round-trip"),
    "missing-server-info": (INFO, "Result does not identify the server in _meta"),
    "missing-client-info": (INFO, "Request does not identify the client in _meta"),
    "missing-mcp-headers": (ERROR, "HTTP request is missing Mcp-Method/Mcp-Name headers"),
    "header-mismatch": (ERROR, "Mcp-Method/Mcp-Name header does not match the body"),
    "legacy-not-found-code": (WARNING, "Resource not found should use -32602"),
    "deprecated-feature": (INFO, "Uses a deprecated feature"),
    "deprecated-transport": (WARNING, "HTTP+SSE transport is deprecated"),
    "nondeterministic-tools": (WARNING, "tools/list order changed between calls"),
}


class _Findings:
    """Collects rule hits, folding repeats into one finding with a count."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._items: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    def add(self, rule: str, detail: str, message_id: int | None = None,
            exchange_id: int | None = None) -> None:
        key = (rule, detail)
        if key in self._items:
            self._items[key]["count"] += 1
            return
        severity, title = RULES[rule]
        self._items[key] = {
            "rule": rule, "severity": severity, "title": title, "detail": detail,
            "session_id": self.session_id, "message_id": message_id,
            "exchange_id": exchange_id, "count": 1,
        }

    def items(self) -> list[dict[str, Any]]:
        return sorted(self._items.values(), key=lambda f: SEVERITY_ORDER[f["severity"]])


def _header(headers: Any, name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def lint_session(q: Query, session_id: str) -> list[dict[str, Any]]:
    session = q.get_session_header(session_id)
    if not session:
        return []
    findings = _Findings(session_id)
    modern = session.get("era") == proto.MODERN
    http = session["transport"] in ("streamable_http", "http_sse")
    request_methods: dict[int, str] = {}
    tool_orders: list[list[str]] = []

    if session["transport"] == "http_sse":
        findings.add("deprecated-transport", "Migrate to Streamable HTTP")

    for message in q.messages_for(session_id):
        body = message["body"]
        mid, xid = message["id"], message["exchange_id"]
        kind, method = message["kind"], message["method"]

        if kind == jsonrpc.INVALID:
            if message["note"] == "not JSON":
                where = "stdout" if session["transport"] == "stdio" else "the stream"
                findings.add("non-json-output", f"Stray output on {where}", mid)
            else:
                findings.add("invalid-jsonrpc", "Missing jsonrpc/id/method structure", mid)
            continue
        if message["note"] == "no matching request":
            findings.add("unmatched-response", f"id {message['rpc_id']}", mid)

        if method in proto.DEPRECATED_FEATURES:
            findings.add("deprecated-feature",
                         f"{proto.DEPRECATED_FEATURES[method]} ({method})", mid, xid)

        if kind == jsonrpc.REQUEST:
            request_methods[xid] = method
            if modern:
                _lint_modern_request(findings, message, body, http)
        elif kind == jsonrpc.NOTIFICATION and modern and method in proto.REMOVED_IN_MODERN:
            findings.add("removed-method", method, mid, xid)
        elif kind == jsonrpc.RESPONSE:
            request_method = request_methods.get(xid)
            if request_method == "tools/list":
                tool_orders.append([str(t.get("name")) for t in proto.tools_from_list(body)])
            if modern:
                _lint_modern_result(findings, message, body, request_method)
        elif kind == jsonrpc.ERROR and modern:
            code, _ = proto.error_of(body)
            if code == -32002 and request_methods.get(xid) == "resources/read":
                findings.add("legacy-not-found-code", "resources/read returned -32002", mid, xid)

    _lint_tool_order(findings, tool_orders)
    return findings.items()


def _lint_modern_request(findings: _Findings, message, body, http: bool) -> None:
    mid, xid, method = message["id"], message["exchange_id"], message["method"]
    if method in proto.REMOVED_IN_MODERN:
        findings.add("removed-method", method, mid, xid)
    if message["direction"] == "s2c":
        detail = method if method in proto.REPLACED_BY_MRTR else f"{method} sent by server"
        findings.add("server-initiated-request", detail, mid, xid)
        return
    if not proto.client_info(body):
        findings.add("missing-client-info", method, mid, xid)
    if http:
        header_method = _header(message["headers"], "Mcp-Method")
        if header_method is None:
            findings.add("missing-mcp-headers", f"Mcp-Method on {method}", mid, xid)
        elif header_method != method:
            findings.add("header-mismatch", f"Mcp-Method {header_method!r} vs {method!r}",
                         mid, xid)
        target = proto.target_of(body)
        if target is not None:
            header_name = _header(message["headers"], "Mcp-Name")
            if header_name is None:
                findings.add("missing-mcp-headers", f"Mcp-Name on {method}", mid, xid)
            elif header_name != target:
                findings.add("header-mismatch", f"Mcp-Name {header_name!r} vs {target!r}",
                             mid, xid)


def _lint_modern_result(findings: _Findings, message, body, request_method) -> None:
    mid, xid = message["id"], message["exchange_id"]
    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    label = request_method or "response"
    if "resultType" not in result:
        findings.add("missing-result-type", label, mid, xid)
    if (request_method in proto.CACHEABLE_METHODS
            and result.get("resultType", proto.RESULT_COMPLETE) == proto.RESULT_COMPLETE
            and ("ttlMs" not in result or "cacheScope" not in result)):
        findings.add("missing-cache-hints", label, mid, xid)
    if not proto.server_info(body, request_method):
        findings.add("missing-server-info", label, mid, xid)


def _lint_tool_order(findings: _Findings, orders: list[list[str]]) -> None:
    for previous, current in zip(orders, orders[1:]):
        if set(previous) == set(current) and previous != current:
            findings.add("nondeterministic-tools",
                         "Same tools returned in a different order (hurts caching)")
            return


def lint(q: Query, session_ids: list[str], min_severity: str = INFO) -> list[dict[str, Any]]:
    limit = SEVERITY_ORDER[min_severity]
    findings = []
    for session_id in session_ids:
        findings.extend(f for f in lint_session(q, session_id)
                        if SEVERITY_ORDER[f["severity"]] <= limit)
    return sorted(findings, key=lambda f: SEVERITY_ORDER[f["severity"]])
