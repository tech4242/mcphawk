import io
import json
import os
import sys
from pathlib import Path

from mcphawk.capture import process, stdio
from mcphawk.capture.stdio import LineFramer, StdioShim
from mcphawk.query import Query

SERVER = str(Path(__file__).resolve().parents[2] / "fixtures" / "echo_server.py")


def lines(*msgs):
    return b"".join(json.dumps(m).encode() + b"\n" for m in msgs)


def run_shim(recorder, stdin_bytes, command=None, **kwargs):
    stdout, stderr = io.BytesIO(), io.BytesIO()
    shim = StdioShim(command or [sys.executable, SERVER, "--api-key", "hunter2"],
                     recorder=recorder, stdin=io.BytesIO(stdin_bytes), stdout=stdout,
                     stderr=stderr, **kwargs)
    code = shim.run()
    return shim, code, stdout.getvalue(), stderr.getvalue()


def test_shim_forwards_verbatim_and_records(recorder, db):
    request = lines(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "x"}},
    )
    shim, code, out, err = run_shim(recorder, request, name="echo")
    assert code == 0
    assert out.startswith(b"booting (stray stdout line)\n")
    assert out.count(b'"jsonrpc"') == 2
    assert b"stderr noise" in err

    q = Query(db)
    session = q.get_session(shim.session_id)
    assert session["name"] == "echo"
    assert session["server_name"] == "echo"
    assert session["client_name"] == "t"
    assert session["transport"] == "stdio"
    assert session["pid"] == os.getpid()
    assert session["ended_at"] is not None
    assert "hunter2" not in session["target"]
    assert [e["status"] for e in session["exchanges"]] == ["ok", "ok"]
    assert session["invalid_count"] == 1  # the stray stdout line
    q.close()


def test_shim_reports_exit_code_and_missing_binary(recorder):
    _, code, _, _ = run_shim(recorder, lines({"jsonrpc": "2.0", "id": 1, "method": "exit"}))
    assert code == 3
    _, code, _, err = run_shim(recorder, b"", command=["/definitely/not/here"])
    assert code == 127
    assert b"cannot start" in err


def test_shim_requires_command(recorder):
    try:
        StdioShim([], recorder=recorder)
    except ValueError as exc:
        assert "no server command" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_run_wrap_maps_signals(monkeypatch):
    class FakeShim:
        def __init__(self, *args, **kwargs):
            pass

        def terminate(self, *args):  # pragma: no cover - never signalled here
            pass

        def run(self):
            return -15

    monkeypatch.setattr(stdio, "StdioShim", FakeShim)
    monkeypatch.setattr(stdio.signal, "signal", lambda *a: None)
    assert stdio.run_wrap(["x"]) == 143


def test_line_framer_edge_cases(monkeypatch):
    seen = []
    framer = LineFramer(seen.append)
    framer.feed(b"a\nb")
    framer.feed(b"c\n\n  \n")
    framer.flush()
    framer.flush()
    assert seen == [b"a", b"bc"]
    monkeypatch.setattr(stdio, "MAX_LINE", 4)
    framer.feed(b"123456")
    assert seen[-1] == b"123456"

    def boom(_):
        raise RuntimeError("disk full")

    LineFramer(boom).feed(b"x\n")  # must not raise


def test_pump_survives_closed_sink():
    class ClosedSink:
        def write(self, _):
            raise BrokenPipeError

        def flush(self):  # pragma: no cover
            pass

        def close(self):
            raise OSError

    seen = []
    stdio._pump(io.BytesIO(b"x\ny\n"), ClosedSink(), LineFramer(seen.append), True)
    assert seen == [b"x", b"y"]


def test_pump_reads_without_read1():
    class Plain:
        def __init__(self):
            self.data = [b"z\n", b""]

        def read(self, _):
            return self.data.pop(0)

    seen = []
    stdio._pump(Plain(), None, LineFramer(seen.append), False)
    assert seen == [b"z"]


def test_find_client_walks_past_launchers():
    me = process.find_client(os.getpid())
    assert me is not None
    assert me.run_key.startswith("pid:")
    assert process.find_client(2**22 + 11) is None


def test_find_client_skips_launcher_chain(monkeypatch):
    class Proc:
        def __init__(self, pid, name, parent=None, cmd=()):
            self.pid, self._name, self._parent, self._cmd = pid, name, parent, list(cmd)

        def name(self):
            return self._name

        def cmdline(self):
            return self._cmd

        def parent(self):
            return self._parent

        def create_time(self):
            return 5.0

    client = Proc(10, "node")
    chain = Proc(12, "uvx", Proc(11, "sh", client))
    monkeypatch.setattr(process.psutil, "Process", lambda pid: chain)
    found = process.find_client(12)
    assert (found.pid, found.name, found.run_key) == (10, "node", "pid:10:5")

    orphan = Proc(20, "uv", Proc(1, "launchd"))
    monkeypatch.setattr(process.psutil, "Process", lambda pid: orphan)
    assert process.find_client(20).pid == 20

    wrapper = Proc(30, "Python", Proc(31, "claude"), cmd=["python", "mcphawk", "wrap"])
    monkeypatch.setattr(process.psutil, "Process", lambda pid: wrapper)
    assert process.find_client(30).name == "claude"

    class NoCmd(Proc):
        def cmdline(self):
            raise process.psutil.AccessDenied()

    guarded = NoCmd(40, "Electron")
    monkeypatch.setattr(process.psutil, "Process", lambda pid: guarded)
    assert process.find_client(40).name == "Electron"

    deep = Proc(50, "sh")
    node = deep
    for i in range(10):
        node._parent = Proc(51 + i, "sh")
        node = node._parent
    monkeypatch.setattr(process.psutil, "Process", lambda pid: deep)
    assert process.find_client(50, max_depth=3).pid == 50
