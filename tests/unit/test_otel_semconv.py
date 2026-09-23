from mcphawk.otel import semconv

EXCHANGE = {
    "id": 7, "session_id": "s1", "initiator": "client", "method": "tools/call",
    "target": "get_weather", "rpc_id": "3", "status": "ok", "error_code": None,
    "error_message": None, "request_tokens": 12, "response_tokens": 40,
}
STDIO = {"id": "s1", "display_name": "weather", "transport": "stdio",
         "protocol_version": "2026-07-28", "client_app": "claude", "client_key": "pid:1"}


def test_ids_are_deterministic_and_valid():
    assert semconv.run_trace_id("pid:1@100") == semconv.run_trace_id("pid:1@100")
    assert semconv.run_trace_id("pid:1@100") != semconv.run_trace_id("pid:1@200")
    assert 0 < semconv.exchange_span_id(7) < 2**64
    assert 0 < semconv.run_trace_id("x") < 2**128
    assert semconv.run_span_id("x") != semconv.exchange_span_id(1)
    assert semconv.session_trace_id("s") > 0


def test_parse_traceparent():
    parsed = semconv.parse_traceparent(
        "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
    assert parsed == (0x4bf92f3577b34da6a3ce929d0e0e4736, 0x00f067aa0ba902b7, 1)
    assert semconv.parse_traceparent("00-" + "0" * 32 + "-00f067aa0ba902b7-01") is None
    assert semconv.parse_traceparent("garbage") is None
    assert semconv.parse_traceparent(None) is None
    assert semconv.request_traceparent("not a dict") is None
    body = {"params": {"_meta": {
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}}}
    assert semconv.request_traceparent(body)[1] == 0x00f067aa0ba902b7


def test_span_name_follows_conventions():
    assert semconv.span_name(EXCHANGE) == "tools/call get_weather"
    assert semconv.span_name({**EXCHANGE, "method": "prompts/get", "target": "p"}) == (
        "prompts/get p")
    assert semconv.span_name({**EXCHANGE, "method": "resources/read",
                              "target": "file:///a"}) == "resources/read"
    assert semconv.span_name({**EXCHANGE, "method": "tools/list", "target": None}) == (
        "tools/list")


def test_error_types():
    assert semconv.error_type(EXCHANGE) is None
    assert semconv.error_type({**EXCHANGE, "status": "tool_error"}) == "tool_error"
    assert semconv.error_type({**EXCHANGE, "status": "error", "error_code": -32602}) == (
        "-32602")
    assert semconv.error_type({**EXCHANGE, "status": "error"}) == "error"
    assert semconv.error_type({**EXCHANGE, "status": "cancelled"}) == "cancelled"


def test_span_and_metric_attributes():
    attributes = semconv.span_attributes(EXCHANGE, STDIO, "pid:1@100")
    assert attributes["mcp.method.name"] == "tools/call"
    assert attributes["gen_ai.tool.name"] == "get_weather"
    assert attributes["gen_ai.operation.name"] == "execute_tool"
    assert attributes["mcp.protocol.version"] == "2026-07-28"
    assert attributes["jsonrpc.request.id"] == "3"
    assert attributes["network.transport"] == "pipe"
    assert attributes["mcphawk.client.name"] == "Claude Code"
    assert attributes["mcphawk.run.key"] == "pid:1@100"
    assert attributes["mcphawk.exchange.url"].endswith("/x/7")
    assert "error.type" not in attributes

    http = {**STDIO, "transport": "streamable_http", "target": "https://[::1]:8443/mcp"}
    failed = {**EXCHANGE, "method": "resources/read", "target": "file:///x",
              "status": "error", "error_code": -32602, "rpc_id": '"a"'}
    attributes = semconv.span_attributes(failed, http, None)
    assert attributes["mcp.resource.uri"] == "file:///x"
    assert attributes["server.address"] == "::1"
    assert attributes["server.port"] == 8443
    assert attributes["network.protocol.name"] == "http"
    assert attributes["rpc.response.status_code"] == "-32602"
    assert attributes["error.type"] == "-32602"
    assert attributes["jsonrpc.request.id"] == "a"
    assert "mcphawk.run.key" not in attributes

    prompt = semconv.span_attributes({**EXCHANGE, "method": "prompts/get", "target": "p",
                                      "status": "input_required"},
                                     {**http, "target": "http://host/mcp"}, None)
    assert prompt["gen_ai.prompt.name"] == "p"
    assert prompt["mcphawk.result.type"] == "input_required"
    assert "server.port" not in prompt
    assert semconv.span_attributes({**EXCHANGE, "method": "ping", "target": "x"},
                                   {**http, "target": ""}, None)["mcp.method.name"] == "ping"

    metrics = semconv.metric_attributes({**EXCHANGE, "status": "tool_error"},
                                        {"id": "s", "display_name": None})
    assert metrics == {"mcp.method.name": "tools/call", "gen_ai.tool.name": "get_weather",
                       "mcphawk.server.name": "unknown", "mcphawk.client.name": "Unknown client",
                       "error.type": "tool_error"}


def message(**overrides):
    base = {"id": 1, "session_id": "s1", "direction": "c2s", "kind": "request",
            "method": "tools/call", "rpc_id": "3", "size": 50, "note": None,
            "body": {"jsonrpc": "2.0", "id": 3, "method": "tools/call"}}
    return {**base, **overrides}


def test_log_fields():
    severity, body, attributes = semconv.log_fields(message(), STDIO, include_payload=False)
    assert (severity, body) == ("INFO", "request tools/call (client to server)")
    assert attributes["mcp.method.name"] == "tools/call"
    assert "mcphawk.message.payload" not in attributes

    error = message(direction="s2c", kind="error", method=None, body={
        "jsonrpc": "2.0", "id": 3, "error": {"code": -32601, "message": "nope"}})
    severity, body, attributes = semconv.log_fields(error, STDIO, include_payload=True)
    assert severity == "ERROR"
    assert body == "error response to id 3 (server to client): nope"
    assert attributes["error.type"] == "-32601"
    assert '"nope"' in attributes["mcphawk.message.payload"]

    tool_error = message(direction="s2c", kind="response", method=None, body={
        "jsonrpc": "2.0", "id": 3, "result": {"isError": True,
                                              "content": [{"type": "text", "text": "bad"}]}})
    severity, body, attributes = semconv.log_fields(tool_error, STDIO, False)
    assert (severity, attributes["error.type"]) == ("ERROR", "tool_error")
    assert body.endswith(": bad")

    invalid = message(kind="invalid", method=None, rpc_id=None, note="not JSON",
                      body="hello")
    severity, body, attributes = semconv.log_fields(invalid, STDIO, True)
    assert severity == "WARN"
    assert body == "invalid invalid (client to server): not JSON"
    assert attributes["mcphawk.message.payload"] == "hello"

    bare_error = message(kind="error", method=None, body={"error": {}})
    assert semconv.log_fields(bare_error, STDIO, False)[2]["error.type"] == "error"
