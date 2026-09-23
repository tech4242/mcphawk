from mcphawk.protocol import jsonrpc


def test_parse_frame_single_and_batch():
    assert jsonrpc.parse_frame('{"jsonrpc":"2.0","id":1,"method":"x"}') == [
        {"jsonrpc": "2.0", "id": 1, "method": "x"}]
    batch = jsonrpc.parse_frame('[{"jsonrpc":"2.0","method":"a"}, 3]')
    assert batch == [{"jsonrpc": "2.0", "method": "a"}, {}]


def test_parse_frame_rejects_non_json_and_scalars():
    assert jsonrpc.parse_frame("Server started on port 3000") is None
    assert jsonrpc.parse_frame("42") is None
    assert jsonrpc.parse_frame(None) is None


def test_classify():
    assert jsonrpc.classify({"jsonrpc": "2.0", "id": 1, "method": "m"}) == jsonrpc.REQUEST
    assert jsonrpc.classify({"jsonrpc": "2.0", "method": "m"}) == jsonrpc.NOTIFICATION
    assert jsonrpc.classify({"jsonrpc": "2.0", "id": None, "method": "m"}) == jsonrpc.NOTIFICATION
    assert jsonrpc.classify({"jsonrpc": "2.0", "id": 1, "result": {}}) == jsonrpc.RESPONSE
    assert jsonrpc.classify({"jsonrpc": "2.0", "id": 1, "error": {"code": 1}}) == jsonrpc.ERROR
    assert jsonrpc.classify({"jsonrpc": "1.0", "id": 1, "method": "m"}) == jsonrpc.INVALID
    assert jsonrpc.classify({"jsonrpc": "2.0", "result": {}}) == jsonrpc.INVALID
    assert jsonrpc.classify({}) == jsonrpc.INVALID


def test_id_key_keeps_types_distinct():
    assert jsonrpc.id_key(1) != jsonrpc.id_key("1")
    assert jsonrpc.id_key(None) is None
