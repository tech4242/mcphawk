from mcphawk.protocol import mcp as proto
from tests.traffic import MODERN, modern_meta, server_meta


def req(method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def res(result, id=1):
    return {"jsonrpc": "2.0", "id": id, "result": result}


def test_era_of_version():
    assert proto.era_of_version("2024-11-05") == proto.LEGACY
    assert proto.era_of_version("2025-11-25") == proto.LEGACY
    assert proto.era_of_version(MODERN) == proto.MODERN
    assert proto.era_of_version("2027-01-01") == proto.MODERN
    assert proto.era_of_version(None) is None


def test_target_of():
    assert proto.target_of(req("tools/call", {"name": "t"})) == "t"
    assert proto.target_of(req("resources/read", {"uri": "file:///a"})) == "file:///a"
    assert proto.target_of(req("prompts/get", {"name": "p"})) == "p"
    assert proto.target_of(req("tools/list")) is None
    assert proto.target_of(req("tools/call", {})) is None


def test_legacy_identity_and_version():
    init = req("initialize", {"protocolVersion": "2025-06-18",
                              "clientInfo": {"name": "cursor", "version": 1}})
    assert proto.client_info(init) == {"name": "cursor", "version": "1"}
    assert proto.protocol_version(init) == "2025-06-18"
    response = res({"protocolVersion": "2025-03-26", "serverInfo": {"name": "srv"}})
    assert proto.server_info(response, "initialize") == {"name": "srv", "version": ""}
    assert proto.negotiated_version(response) == "2025-03-26"
    assert proto.client_info(req("tools/list", {"clientInfo": {"name": "x"}})) is None


def test_modern_identity_and_version():
    call = req("tools/call", {"name": "t", "_meta": modern_meta("claude-code")})
    assert proto.client_info(call) == {"name": "claude-code", "version": "2.1.0"}
    assert proto.protocol_version(call) == MODERN
    assert proto.server_info(res({"_meta": server_meta("wx")})) == {
        "name": "wx", "version": "1.2.0"}
    discover = res({"serverInfo": {"name": "d", "version": "2"}})
    assert proto.server_info(discover, "server/discover")["name"] == "d"
    assert proto.server_info(res({"content": []}), "tools/call") is None
    assert proto.server_info(res({"serverInfo": {"version": "1"}})) is None


def test_result_type_and_mrtr_fields():
    assert proto.result_type(res({})) == proto.RESULT_COMPLETE
    interim = res({"resultType": "input_required", "requestState": "s",
                   "inputRequests": {"a": {"method": "elicitation/create"}}})
    assert proto.result_type(interim) == proto.RESULT_INPUT_REQUIRED
    assert proto.request_state(interim) == "s"
    assert proto.input_requests(interim) == {"a": {"method": "elicitation/create"}}
    assert proto.request_state(req("tools/call", {"requestState": "s"})) == "s"
    assert proto.request_state(req("tools/call", {})) is None


def test_errors_and_tool_errors():
    error = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "nope"}}
    assert proto.error_of(error) == (-32601, "nope")
    assert proto.error_of({"error": {"code": "x"}}) == (None, None)
    failed = res({"isError": True, "content": [{"type": "image"}, {"type": "text", "text": "boom"}]})
    assert proto.is_tool_error(failed)
    assert proto.tool_error_text(failed) == "boom"
    assert proto.tool_error_text(res({"isError": True})) is None


def test_list_helpers():
    listing = res({"tools": [{"name": "a"}, "junk"], "instructions": "hi"})
    assert proto.tools_from_list(listing) == [{"name": "a"}]
    assert proto.tools_from_list(res({"tools": "nope"})) == []
    assert proto.instructions_of(listing) == "hi"
    assert proto.instructions_of(res({})) is None
    traced = req("tools/call", {"_meta": {"traceparent": "00-abc-def-01"}})
    assert proto.trace_parent(traced) == "00-abc-def-01"
    assert proto.trace_parent(req("tools/list")) is None
