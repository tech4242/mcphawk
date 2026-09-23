import json
import os
import stat
import sys

import pytest

from mcphawk.install import clients as cl
from mcphawk.install import installer as ins

HAWK = ["/opt/bin/mcphawk"]


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(cl.platform, "system", lambda: "Darwin")
    support = home / "Library" / "Application Support"

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data))
        return path

    write(support / "Claude" / "claude_desktop_config.json", {"mcpServers": {
        "fs": {"command": "npx", "args": ["-y", "@mcp/fs", "/tmp"], "env": {"X": "1"}},
        "off": {"command": "x", "disabled": True},
        "self": {"command": "mcphawk", "args": ["mcp"]},
    }, "otherSetting": True})
    os.chmod(support / "Claude" / "claude_desktop_config.json", 0o600)
    write(home / ".claude.json", {
        "mcpServers": {
            "linear": {"type": "http", "url": "https://mcp.linear.app/mcp"},
            "local": {"type": "http", "url": "http://localhost:3000/mcp"},
            "keyed": {"type": "http", "url": "https://api.test/mcp",
                      "headers": {"Authorization": "Bearer x"}},
        },
        "projects": {"/work/app": {"mcpServers": {
            "ctx": {"type": "stdio", "command": "uvx", "args": ["ctx-server"]}}},
            "/work/empty": {"allowedTools": []}},
    })
    write(home / ".cursor" / "mcp.json", {"mcpServers": {
        "weird": {"something": "else"}, "notadict": 3}})
    write(support / "Code" / "User" / "mcp.json",
          '{\n  // my servers\n  "servers": {\n    "gh": {"type": "stdio", "command": "gh-mcp",},\n  },\n}')
    return home


def by_name(changes):
    return {(c.table.client, c.server): c for c in changes}


def test_plan_install_defaults(home):
    changes = by_name(ins.plan(home=home, command=HAWK, registry={}))
    fs = changes[("claude-desktop", "fs")]
    assert fs.action == ins.WRAP
    assert fs.after["command"] == "/opt/bin/mcphawk"
    assert fs.after["args"] == ["wrap", "--name", "fs", "--", "npx", "-y", "@mcp/fs", "/tmp"]
    assert fs.after["env"] == {"X": "1"}
    assert changes[("claude-desktop", "off")].reason == "disabled"
    assert changes[("claude-desktop", "self")].reason == "this is MCPHawk itself"
    assert changes[("claude-code", "linear")].reason.startswith("HTTP server")
    assert changes[("claude-code", "ctx")].table.scope == "local:/work/app"
    assert changes[("cursor", "weird")].reason == "unrecognised server entry"
    assert changes[("vscode", "gh")].action == ins.WRAP


def test_plan_include_http(home):
    registry = {"local": "http://elsewhere/mcp"}
    changes = by_name(ins.plan(home=home, command=HAWK, include_http=True, registry=registry))
    assert "OAuth" in changes[("claude-code", "linear")].reason
    local = changes[("claude-code", "local")]
    assert local.action == ins.PROXY
    assert local.after["url"] == "http://127.0.0.1:8484/p/local-2"
    assert changes[("claude-code", "keyed")].action == ins.PROXY
    assert registry["local-2"] == "http://localhost:3000/mcp"
    forced = by_name(ins.plan(home=home, command=HAWK, force_http=True, registry={}))
    assert forced[("claude-code", "linear")].action == ins.PROXY


def test_install_then_uninstall_roundtrip(home):
    desktop = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    original = json.loads(desktop.read_text())
    registry = {}
    changes = ins.plan(home=home, command=HAWK, include_http=True, registry=registry)
    notes = ins.apply(changes, registry)
    assert any("comments are not preserved" in n for n in notes)
    assert sum(n.startswith("updated") for n in notes) == 3
    assert stat.S_IMODE(desktop.stat().st_mode) == 0o600
    assert len(list((home.parent / "mcphawk-home" / "backups").iterdir())) == 3
    assert ins.load_registry() == registry

    installed = json.loads(desktop.read_text())
    assert installed["otherSetting"] is True
    again = by_name(ins.plan(home=home, command=HAWK, include_http=True, registry=registry))
    assert again[("claude-desktop", "fs")].reason == "already wrapped"
    assert again[("claude-code", "local")].reason == "already proxied"

    # the user edits the config while installed; uninstall must keep it
    installed["mcpServers"]["fs"]["env"]["Y"] = "2"
    desktop.write_text(json.dumps(installed))

    undo = ins.plan(uninstall=True, home=home, registry=ins.load_registry())
    ins.apply(undo)
    restored = json.loads(desktop.read_text())
    assert restored["mcpServers"]["fs"]["command"] == "npx"
    assert restored["mcpServers"]["fs"]["args"] == original["mcpServers"]["fs"]["args"]
    assert restored["mcpServers"]["fs"]["env"] == {"X": "1", "Y": "2"}
    code = json.loads((home / ".claude.json").read_text())
    assert code["mcpServers"]["local"]["url"] == "http://localhost:3000/mcp"
    assert code["projects"]["/work/app"]["mcpServers"]["ctx"]["command"] == "uvx"
    reasons = {c.reason for c in ins.plan(uninstall=True, home=home, registry={})}
    assert reasons == {"not routed through MCPHawk"}


def test_uninstall_with_missing_registry_entry(home):
    registry = {}
    ins.apply(ins.plan(home=home, command=HAWK, include_http=True, registry=registry), registry)
    changes = by_name(ins.plan(uninstall=True, home=home, registry={}))
    assert "missing from registry" in changes[("claude-code", "local")].reason


def test_project_scope_files(home, tmp_path):
    project = tmp_path / "proj"
    (project / ".vscode").mkdir(parents=True)
    (project / ".vscode" / "mcp.json").write_text('{"servers": {"p": {"command": "p"}}}')
    (project / ".mcp.json").write_text("not json")
    changes = ins.plan(home=home, project=project, command=HAWK, registry={},
                       clients=(cl.VSCODE, cl.CLAUDE_CODE, cl.CURSOR))
    scopes = {(c.table.client, c.table.scope) for c in changes}
    assert ("vscode", "project") in scopes
    assert ("claude-code", "project") not in scopes  # unparsable file is skipped


def test_apply_skips_file_that_became_unparsable(home):
    changes = ins.plan(home=home, command=HAWK, registry={}, clients=(cl.CURSOR, cl.CLAUDE_DESKTOP))
    desktop = next(c for c in changes if c.after).table.path
    desktop.write_text("{broken")
    notes = ins.apply(changes)
    assert notes == [f"skipped {desktop}: could not parse it"]


def test_backup_names_do_not_collide(home):
    path = home / ".cursor" / "mcp.json"
    first, second = ins.backup(path), ins.backup(path)
    assert first != second
    assert second.read_text() == path.read_text()


def test_wrapped_original_variants():
    assert ins.wrapped_original({"command": "uvx", "args": [
        "mcphawk", "wrap", "--", "srv", "-v"]}) == ("srv", ["-v"])
    assert ins.wrapped_original({"command": "python", "args": [
        "-m", "mcphawk", "wrap", "--"]}) is None
    assert ins.wrapped_original({"command": "mcphawk", "args": ["mcp"]}) is None
    assert ins.wrapped_original({"command": None}) is None
    legacy = {"command": "/venv/bin/mcphawk", "args": ["wrap", "npx", "-y", "ctx7"]}
    assert ins.wrapped_original(legacy) == ("npx", ["-y", "ctx7"])
    debug = {"command": "mcphawk", "args": ["wrap", "--debug", "srv"]}
    assert ins.wrapped_original(debug) == ("srv", [])
    assert ins.wrapped_original({"command": "mcphawk", "args": ["wrap"]}) is None


def test_mcphawk_command_resolution(monkeypatch, tmp_path):
    script = tmp_path / "mcphawk"
    script.write_text("")
    monkeypatch.setattr(sys, "argv", [str(script)])
    assert ins.mcphawk_command() == [str(script.resolve())]
    monkeypatch.setattr(sys, "argv", ["pytest"])
    monkeypatch.setattr(ins.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert ins.mcphawk_command() == ["/usr/bin/mcphawk"]
    monkeypatch.setattr(ins.shutil, "which", lambda name: None)
    assert ins.mcphawk_command() == [sys.executable, "-m", "mcphawk"]
    monkeypatch.setattr(sys, "executable", "/Users/x/.cache/uv/archive-v0/abc/bin/python")
    assert ins.mcphawk_command() == ["uvx", "mcphawk"]


def test_registry_ignores_garbage():
    ins.registry_path().write_text("[1, 2")
    assert ins.load_registry() == {}
    ins.registry_path().write_text('{"a": "http://x", "b": 3}')
    assert ins.load_registry() == {"a": "http://x"}


def test_client_paths_per_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(cl.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert cl.config_files(cl.CLAUDE_DESKTOP, tmp_path, None)[0][1] == (
        tmp_path / "cfg" / "Claude" / "claude_desktop_config.json")
    monkeypatch.setattr(cl.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert cl.config_files(cl.VSCODE, tmp_path, None)[0][1] == (
        tmp_path / "roaming" / "Code" / "User" / "mcp.json")
    with pytest.raises(ValueError):
        cl.config_files("emacs", tmp_path, None)


def test_jsonc_parsing():
    text = '{"a": "http://x // not a comment", /* c */ "b": [1, 2,], // tail\n}'
    assert cl.loads_jsonc(text) == {"a": "http://x // not a comment", "b": [1, 2]}
    assert cl.has_comments(text)
    assert not cl.has_comments('{"a": "//"}')
    assert cl.loads_jsonc("  ") == {}
    table = cl.ServerTable("cursor", "user", tmp := None, ("mcpServers",))
    assert table.label() == "cursor (user)"
    assert tmp is None
