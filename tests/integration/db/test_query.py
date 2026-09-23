import os

from mcphawk.query import HUNG_AFTER_S, IDLE_AFTER_S, Query, resolve_scope
from mcphawk.store import C2S, S2C
from tests.traffic import Clock, frame, legacy_session, modern_session


def test_list_sessions_counts_and_filters(recorder, query):
    clock = Clock()
    legacy = legacy_session(recorder, clock)
    modern = modern_session(recorder, clock, name="other")
    sessions = query.list_sessions()
    assert [s["id"] for s in sessions] == [modern, legacy]
    by_id = {s["id"]: s for s in sessions}
    assert by_id[legacy]["exchange_count"] == 5
    assert by_id[legacy]["error_count"] == 2
    assert by_id[legacy]["display_name"] == "weather"
    assert by_id[legacy]["tokens"] > 0
    assert [s["id"] for s in query.list_sessions(server="other")] == [modern]
    assert [s["id"] for s in query.list_sessions(server="weather-server")] == [legacy]


def test_liveness_rules(recorder, db):
    clock = Clock(start=1000.0)
    alive = recorder.open_session(capture="wrap", transport="stdio", pid=os.getpid(), ts=clock())
    dead = recorder.open_session(capture="wrap", transport="stdio", pid=2**22 + 7, ts=clock())
    idle = recorder.open_session(capture="proxy", transport="streamable_http", ts=clock())
    ended = recorder.open_session(capture="proxy", transport="streamable_http", ts=clock())
    recorder.end_session(ended, ts=clock())
    q = Query(db, now=lambda: 1000.0 + IDLE_AFTER_S + 60)
    live = {s["id"]: s["live"] for s in q.list_sessions()}
    assert live == {alive: True, dead: False, idle: False, ended: False}
    q.close()


def test_hung_and_abandoned_calls(recorder, db):
    sid = recorder.open_session(capture="proxy", transport="streamable_http", ts=1000.0)
    recorder.record(sid, C2S, frame(id=1, method="tools/call", params={"name": "slow"}),
                    ts=1000.0)
    fresh = Query(db, now=lambda: 1001.0)
    assert fresh.get_session(sid)["exchanges"][0]["status"] == "pending"
    later = Query(db, now=lambda: 1000.0 + HUNG_AFTER_S + 1)
    exchange = later.get_session(sid)["exchanges"][0]
    assert exchange["status"] == "hung"
    assert exchange["duration_ms"] > HUNG_AFTER_S * 1000
    assert [e["id"] for e in later.exchanges(status="hung")] == [exchange["id"]]
    assert later.exchanges(status="abandoned") == []
    recorder.end_session(sid, ts=1002.0)
    assert later.get_exchange(exchange["id"])["status"] == "abandoned"
    for q in (fresh, later):
        q.close()


def test_get_session_and_exchange_details(recorder, query):
    sid = modern_session(recorder)
    session = query.get_session(sid)
    assert session["message_count"] == 8
    assert session["notification_count"] == 0
    assert session["invalid_count"] == 0
    retry = [e for e in session["exchanges"] if e["method"] == "tools/call"][-1]
    detail = query.get_exchange(retry["id"])
    assert detail["request"]["body"]["params"]["requestState"] == "state-1"
    assert detail["response"]["body"]["result"]["content"][0]["text"] == "Rain"
    assert [c["status"] for c in detail["chain"]] == ["input_required", "ok"]
    assert detail["session"]["id"] == sid
    first = query.get_exchange(session["exchanges"][0]["id"])
    assert first["chain"] == []
    assert query.get_exchange(9999) is None
    assert query.get_session("nope") is None
    assert query.get_message(9999) is None


def test_pending_exchange_has_no_response(recorder, query):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(sid, C2S, frame(id=1, method="tools/list"))
    detail = query.get_exchange(query.get_session(sid)["exchanges"][0]["id"])
    assert detail["response"] is None


def test_exchange_filters(recorder, query):
    legacy_session(recorder)
    assert len(query.exchanges(method="tools/call")) == 3
    assert len(query.exchanges(target="get_weather")) == 2
    assert [e["status"] for e in query.exchanges(status="tool_error")] == ["tool_error"]
    assert len(query.exchanges(text="Berlin")) == 1
    assert query.exchanges(text="100%_nothing") == []
    assert query.exchanges(status="pending") == []
    ordered = query.exchanges()
    assert ordered[0]["method"] == "initialize"
    assert ordered[0]["server"] == "weather"


def test_runs_group_sessions(recorder, query):
    clock = Clock()
    a = legacy_session(recorder, clock, run_key="pid:42", client_app="claude")
    b = modern_session(recorder, clock, run_key="pid:42", client_app="claude", name="search")
    solo = legacy_session(recorder, clock, name="solo")
    runs = {r["run_key"]: r for r in query.list_runs()}
    assert set(runs) == {"pid:42", f"session:{solo}"}
    assert runs["pid:42"]["session_count"] == 2
    assert runs["pid:42"]["servers"] == ["search", "weather"]
    assert runs["pid:42"]["exchange_count"] == 9
    assert runs["pid:42"]["client_app"] == "claude"

    run = query.get_run("pid:42")
    assert [s["id"] for s in run["sessions"]] == [a, b]
    times = [e["started_at"] for e in run["timeline"]]
    assert times == sorted(times)
    assert run["client_app"] == "claude"
    assert query.get_run(f"session:{solo}")["sessions"][0]["id"] == solo
    assert query.get_run("pid:0") is None


def test_hidden_sessions_are_excluded(recorder, query):
    sid = recorder.open_session(capture="wrap", transport="stdio")
    recorder.record(sid, C2S, frame(id=1, method="initialize", params={}))
    recorder.record(sid, S2C, frame(id=1, result={"serverInfo": {"name": "mcphawk"}}))
    assert query.list_sessions() == []
    assert query.list_runs() == []
    assert query.exchanges() == []
    assert query.messages() == []
    assert len(query.list_sessions(include_hidden=True)) == 1
    assert query.stats()["sessions"] == 0


def test_messages_tail_and_stats(recorder, query):
    sid = legacy_session(recorder)
    assert query.latest_message_id() == 11
    tail = query.messages(after_id=9)
    assert [m["id"] for m in tail] == [10, 11]
    assert query.messages(session_id=sid, limit=2)[0]["method"] == "initialize"
    assert len(query.messages_for(sid, kind="notification")) == 1
    stats = query.stats()
    assert stats == {"sessions": 1, "exchanges": 5, "messages": 11, "errors": 2}
    assert query.responses_for("tools/list", []) == []
    query.clear()
    assert query.stats()["messages"] == 0
    assert query.latest_message_id() == 0


def test_resolve_scope(recorder, query):
    sid = legacy_session(recorder, run_key="pid:1")
    assert [s["id"] for s in resolve_scope(query, session_id=sid)] == [sid]
    assert resolve_scope(query, session_id="missing") == []
    assert [s["id"] for s in resolve_scope(query, run_key="pid:1")] == [sid]
    assert [s["id"] for s in resolve_scope(query)] == [sid]
