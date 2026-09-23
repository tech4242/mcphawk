from mcphawk import runs
from mcphawk.analysis import cost, problems
from mcphawk.store import C2S, S2C
from tests.traffic import frame, modern_meta

GAP = runs.RUN_GAP_S


def call(recorder, sid, ts, rpc_id, name="t", error=False, client=None):
    params = {"name": name}
    if client:
        params["_meta"] = modern_meta(client)
    recorder.record(sid, C2S, frame(id=rpc_id, method="tools/call", params=params), ts=ts)
    result = ({"error": {"code": -1, "message": "boom"}} if error
              else {"result": {"content": []}})
    recorder.record(sid, S2C, frame(id=rpc_id, **result), ts=ts + 0.1)


def stdio(recorder, client_key, name, ts, app="claude"):
    return recorder.open_session(capture="wrap", transport="stdio", name=name,
                                 client_key=client_key, client_app=app, ts=ts)


def test_one_client_many_servers_is_one_run(recorder, query):
    a = stdio(recorder, "pid:1", "fs", 1000)
    b = stdio(recorder, "pid:1", "github", 1001)
    call(recorder, a, 1002, 1)
    call(recorder, b, 1003, 1, error=True)
    [run] = runs.list_runs(query, now=1010)
    assert run["run_key"] == "pid:1@1000"
    assert run["client"] == "Claude Code"
    assert run["servers"] == ["fs", "github"]
    assert (run["exchange_count"], run["error_count"]) == (2, 1)
    assert run["started_at"] == 1000
    assert run["last_seen_at"] == 1003.1


def test_idle_gap_splits_runs_and_keys_are_stable(recorder, query):
    fs = stdio(recorder, "pid:1", "fs", 1000)
    call(recorder, fs, 1001, 1)
    call(recorder, fs, 1001 + GAP + 60, 2, name="later")
    newest, oldest = runs.list_runs(query, now=1001 + GAP + 70)
    assert oldest["run_key"] == "pid:1@1000"
    assert newest["run_key"] == f"pid:1@{int(1001 + GAP + 60)}"
    assert oldest["exchange_count"] == newest["exchange_count"] == 1

    # more traffic in the later run leaves both keys unchanged
    call(recorder, fs, 1001 + GAP + 90, 3)
    keys = [r["run_key"] for r in runs.list_runs(query)]
    assert keys == [newest["run_key"], oldest["run_key"]]

    detail = runs.get_run(query, newest["run_key"])
    assert [e["target"] for e in detail["timeline"]] == ["later", "t"]
    assert [s["id"] for s in detail["sessions"]] == [fs]
    assert runs.get_run(query, "pid:1@1") is None


def test_live_only_for_the_latest_run_of_a_live_client(recorder, query, monkeypatch):
    fs = stdio(recorder, "pid:1", "fs", 1000)
    call(recorder, fs, 1001, 1)
    call(recorder, fs, 2000, 2)
    monkeypatch.setattr(query, "_is_live", lambda session: True)
    newest, oldest = runs.list_runs(query, now=2010)
    assert newest["live"] and not oldest["live"]
    [newest, oldest] = runs.list_runs(query, now=2000 + GAP + 1)
    assert not newest["live"]


def test_http_sessions_join_the_same_clients_process_group(recorder, query):
    fs = stdio(recorder, "pid:9", "fs", 1000)
    call(recorder, fs, 1001, 1, client="claude-code")  # stdio session learns the client name
    web = recorder.open_session(capture="proxy", transport="streamable_http",
                                name="remote", ts=1002)
    call(recorder, web, 1003, 1, client="claude-code")
    other = recorder.open_session(capture="proxy", transport="streamable_http",
                                  name="elsewhere", ts=1004)
    call(recorder, other, 1005, 1, client="cursor-vscode")
    by_client = {r["client"]: r for r in runs.list_runs(query)}
    assert by_client["Claude Code"]["servers"] == ["fs", "remote"]
    assert by_client["Cursor"]["run_key"].startswith("client:cursor-vscode@")


def test_http_sessions_far_apart_stay_separate(recorder, query):
    fs = stdio(recorder, "pid:9", "fs", 1000)
    call(recorder, fs, 1001, 1, client="claude-code")
    late = recorder.open_session(capture="proxy", transport="streamable_http",
                                 name="remote", ts=1001 + 10 * GAP)
    call(recorder, late, 1002 + 10 * GAP, 1, client="claude-code")
    assert len(runs.list_runs(query)) == 2


def test_labels_and_fallback_groups(recorder, query):
    anon = recorder.open_session(capture="sniff", transport="unknown", ts=1000)
    call(recorder, anon, 1001, 1)
    replay = recorder.open_session(capture="replay", transport="stdio",
                                   client_key="replay:4", ts=1002)
    call(recorder, replay, 1003, 1)
    custom = stdio(recorder, "pid:3", "x", 1004, app="my-agent")
    call(recorder, custom, 1005, 1)
    labels = {r["run_key"].split("@")[0]: r["client"] for r in runs.list_runs(query)}
    assert labels == {f"session:{anon}": "Unknown client", "replay:4": "Replay",
                      "pid:3": "my-agent"}


def test_limit_and_empty(recorder, query):
    assert runs.list_runs(query) == []
    for i in range(3):
        sid = stdio(recorder, f"pid:{i}", "fs", 1000 + i)
        call(recorder, sid, 1000.5 + i, 1)
    assert len(runs.list_runs(query, limit=2)) == 2


def test_analyses_only_see_the_runs_window(recorder, query):
    fs = stdio(recorder, "pid:1", "fs", 1000)
    call(recorder, fs, 1001, 1, name="early", error=True)
    call(recorder, fs, 1001 + 2 * GAP, 2, name="late")
    newest, oldest = runs.list_runs(query)

    scope = runs.resolve_scope(query, run_key=newest["run_key"])
    assert [s["id"] for s in scope.sessions] == [fs]
    assert scope.since == newest["started_at"] - 1

    late_problems = problems.find_problems(query, run_key=newest["run_key"],
                                           include_lint=False)
    early_problems = problems.find_problems(query, run_key=oldest["run_key"],
                                            include_lint=False)
    assert late_problems["total"] == 0
    assert early_problems["total"] == 1

    late_cost = cost.context_cost(query, run_key=newest["run_key"])
    assert [c["tool"] for c in late_cost["servers"][0]["calls"]] == ["late"]

    assert runs.resolve_scope(query, run_key="nope@1").sessions == []
    assert [s["id"] for s in runs.resolve_scope(query, session_id=fs).sessions] == [fs]
    assert runs.resolve_scope(query, session_id="missing").sessions == []
    assert [s["id"] for s in runs.resolve_scope(query).sessions] == [fs]
