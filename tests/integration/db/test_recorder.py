import json

from mcphawk.protocol.masking import MASK
from mcphawk.store import C2S, S2C, Recorder, connect
from tests.traffic import Clock, frame, legacy_session, modern_session


def rows(db, sql, params=()):
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def test_schema_is_created_once(db):
    connect(db).close()
    conn = connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_legacy_session_pairs_and_identifies(db, recorder):
    sid = legacy_session(recorder)
    session = rows(db, "SELECT * FROM sessions WHERE id = ?", (sid,))[0]
    assert session["client_name"] == "claude-ai"
    assert session["server_name"] == "weather-server"
    assert session["protocol_version"] == "2025-06-18"
    assert session["era"] == "legacy"

    exchanges = rows(db, "SELECT * FROM exchanges WHERE session_id = ? ORDER BY id", (sid,))
    assert [e["method"] for e in exchanges] == [
        "initialize", "tools/list", "tools/call", "tools/call", "tools/call"]
    assert [e["status"] for e in exchanges] == ["ok", "ok", "ok", "error", "tool_error"]
    assert exchanges[2]["target"] == "get_weather"
    assert exchanges[2]["duration_ms"] == 250.0
    assert exchanges[3]["error_code"] == -32602
    assert exchanges[4]["error_message"] == "unknown city"
    assert all(e["response_msg_id"] for e in exchanges)

    messages = rows(db, "SELECT * FROM messages WHERE session_id = ?", (sid,))
    assert len(messages) == 11
    assert all(m["exchange_id"] for m in messages if m["kind"] != "notification")


def test_modern_session_identity_and_mrtr_chain(db, recorder):
    sid = modern_session(recorder, headers=True)
    session = rows(db, "SELECT * FROM sessions WHERE id = ?", (sid,))[0]
    assert session["era"] == "modern"
    assert session["client_name"] == "claude-code"
    assert session["server_name"] == "weather"

    calls = rows(db, "SELECT * FROM exchanges WHERE method = 'tools/call' ORDER BY id")
    first, retry = calls
    assert first["status"] == "input_required"
    assert retry["status"] == "ok"
    assert retry["parent_id"] == first["id"]
    assert retry["chain_root_id"] == first["id"]

    headers = rows(db, "SELECT headers FROM messages WHERE method = 'tools/call'")[0]
    parsed = json.loads(headers["headers"])
    assert parsed["Authorization"] == MASK
    assert parsed["Mcp-Name"] == "get_weather"


def test_three_step_chain_keeps_root(db, recorder):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    for i, state in enumerate(["a", "b"]):
        params = {"name": "t"}
        if i:
            params["requestState"] = "a"
        recorder.record(sid, C2S, frame(id=i, method="tools/call", params=params))
        recorder.record(sid, S2C, frame(id=i, result={
            "resultType": "input_required", "requestState": state}))
    recorder.record(sid, C2S, frame(id=9, method="tools/call", params={
        "name": "t", "requestState": "b"}))
    chain = rows(db, "SELECT id, parent_id, chain_root_id FROM exchanges ORDER BY id")
    assert chain[1]["parent_id"] == chain[0]["id"]
    assert chain[2]["parent_id"] == chain[1]["id"]
    assert chain[2]["chain_root_id"] == chain[0]["id"]


def test_invalid_batch_unmatched_and_cancel(db, recorder):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    assert recorder.record(sid, S2C, "Listening on stdio...") != []
    assert recorder.record(sid, S2C, "   ") == []
    ids = recorder.record(sid, C2S, json.dumps([
        {"jsonrpc": "2.0", "id": 1, "method": "a"},
        {"jsonrpc": "2.0", "id": 2, "method": "b"}]))
    assert len(ids) == 2
    recorder.record(sid, S2C, frame(id=99, result={}))
    recorder.record(sid, C2S, frame(method="notifications/cancelled", params={
        "requestId": 2, "reason": "user aborted"}))
    recorder.record(sid, C2S, frame(method="notifications/cancelled", params={"requestId": 7}))
    recorder.record(sid, S2C, b'{"jsonrpc":"2.0","id":1,"result":{}}')

    messages = rows(db, "SELECT kind, note FROM messages ORDER BY id")
    assert messages[0] == {"kind": "invalid", "note": "not JSON"}
    assert messages[1]["note"] == "batch of 2"
    assert messages[3]["note"] == "no matching request"
    statuses = rows(db, "SELECT method, status, error_message FROM exchanges ORDER BY id")
    assert statuses == [
        {"method": "a", "status": "ok", "error_message": None},
        {"method": "b", "status": "cancelled", "error_message": "user aborted"},
    ]


def test_server_initiated_request_pairs_with_client_response(db, recorder):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(sid, S2C, frame(id="s1", method="sampling/createMessage", params={}))
    recorder.record(sid, C2S, frame(id="s1", result={"content": {}}))
    exchange = rows(db, "SELECT * FROM exchanges")[0]
    assert exchange["initiator"] == "server"
    assert exchange["status"] == "ok"


def test_masking_can_be_disabled(db):
    rec = Recorder(db, mask=False)
    sid = rec.open_session(capture="wrap", transport="stdio", target="srv --token abc")
    rec.record(sid, C2S, frame(id=1, method="x", params={"api_key": "abc"}),
               headers={"Authorization": "Bearer abcdefghijklmnop"})
    msg = rows(db, "SELECT body, headers FROM messages")[0]
    assert '"abc"' in msg["body"]
    assert "Bearer" in msg["headers"]
    rec.close()


def test_mcphawk_own_server_is_hidden(db, recorder):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(sid, C2S, frame(id=1, method="initialize", params={}))
    recorder.record(sid, S2C, frame(id=1, result={"serverInfo": {"name": "mcphawk"}}))
    assert rows(db, "SELECT hidden FROM sessions")[0]["hidden"] == 1


def test_end_session_and_callback(db):
    seen = []
    rec = Recorder(db, on_record=seen.append)
    sid = rec.open_session(capture="wrap", transport="stdio", client_key="pid:1")
    rec.record(sid, C2S, frame(id=1, method="x"))
    rec.end_session(sid, ts=5.0)
    session = rows(db, "SELECT client_key, ended_at FROM sessions")[0]
    assert session == {"client_key": "pid:1", "ended_at": 5.0}
    assert seen == [{"session_id": sid, "message_id": 1}]
    rec.close()


def test_recorders_in_parallel_share_the_database(db):
    a, b = Recorder(db), Recorder(db)
    clock = Clock()
    legacy_session(a, clock)
    legacy_session(b, clock)
    assert rows(db, "SELECT COUNT(*) AS n FROM sessions")[0]["n"] == 2
    a.close()
    b.close()


def test_response_recorded_before_its_request_is_paired(db, recorder):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(sid, S2C, frame(id=5, result={"content": []}), ts=10.5)
    recorder.record(sid, C2S, frame(id=5, method="tools/call", params={"name": "t"}), ts=10.4)
    exchange = rows(db, "SELECT * FROM exchanges")[0]
    assert exchange["status"] == "ok"
    assert exchange["response_msg_id"] == 1
    assert exchange["duration_ms"] == 100.0
    notes = rows(db, "SELECT note, exchange_id FROM messages ORDER BY id")
    assert notes == [{"note": None, "exchange_id": 1}, {"note": None, "exchange_id": 1}]


def test_early_responses_are_bounded(db, recorder, monkeypatch):
    from mcphawk.store import recorder as rec_mod

    monkeypatch.setattr(rec_mod, "MAX_EARLY", 2)
    sid = recorder.open_session(capture="wrap", transport="stdio")
    for i in range(4):
        recorder.record(sid, S2C, frame(id=i, result={}))
    assert len(recorder._sessions[sid].early) == 2
