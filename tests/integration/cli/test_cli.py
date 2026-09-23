import json

import pytest
from typer.testing import CliRunner

from mcphawk import __version__, cli
from mcphawk.install import clients as cl
from tests.traffic import legacy_session

runner = CliRunner()


def test_version():
    result = runner.invoke(cli.app, ["--version"])
    assert result.output.strip() == f"mcphawk {__version__}"


def test_default_command_runs_up(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    result = runner.invoke(cli.app, [])
    assert result.exit_code == 0, result.output
    assert calls[0]["port"] == 8484
    assert "http://127.0.0.1:8484" in result.output


def test_up_options(monkeypatch):
    calls, sniffers = [], []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    monkeypatch.setattr(cli, "_start_sniffer", lambda *a: sniffers.append(a))
    monkeypatch.setattr(cli.installer, "load_registry", lambda: {"remote": "http://x"})
    result = runner.invoke(cli.app, ["up", "--port", "9001", "--host", "0.0.0.0",
                                     "--no-mcp", "--sniff", "3000", "--sniff", "3001"])
    assert result.exit_code == 0, result.output
    assert calls[0]["host"] == "0.0.0.0"
    assert sniffers[0][0] == "tcp port 3000 or tcp port 3001"
    assert "proxying  remote" in result.output
    assert "  MCP " not in result.output


def test_wrap_passes_command(monkeypatch):
    seen = {}

    def fake_run_wrap(command, name=None, mask=True):
        seen.update(command=command, name=name, mask=mask)
        return 4

    monkeypatch.setattr("mcphawk.capture.stdio.run_wrap", fake_run_wrap)
    result = runner.invoke(cli.app, ["wrap", "--name", "fs", "--no-mask", "--",
                                     "npx", "-y", "server", "--flag"])
    assert result.exit_code == 4
    assert seen == {"command": ["npx", "-y", "server", "--flag"], "name": "fs", "mask": False}
    legacy = runner.invoke(cli.app, ["wrap", "python", "server.py", "--port", "1"])
    assert seen["command"] == ["python", "server.py", "--port", "1"]
    assert legacy.exit_code == 4
    empty = runner.invoke(cli.app, ["wrap"])
    assert empty.exit_code == 2


def test_proxy_command(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    result = runner.invoke(cli.app, ["proxy", "--target", "http://x/mcp", "--name", "x"])
    assert "http://127.0.0.1:8485/p/x" in result.output
    assert calls[0]["port"] == 8485


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(cl.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cli.installer.Path, "home", lambda: home)
    cursor = home / ".cursor" / "mcp.json"
    cursor.parent.mkdir(parents=True)
    cursor.write_text(json.dumps({"mcpServers": {
        "fs": {"command": "npx", "args": ["fs"]},
        "web": {"url": "http://localhost:3000/mcp"}}}))
    monkeypatch.setattr(cli.installer, "mcphawk_command", lambda: ["/bin/mcphawk"])
    return cursor


def test_install_dry_run_confirm_and_uninstall(fake_home):
    dry = runner.invoke(cli.app, ["install", "--dry-run", "--include-http"])
    assert "2 server(s) will be recorded. Dry run" in dry.output
    assert "fs                       recorded (stdio wrapper)" in dry.output
    assert json.loads(fake_home.read_text())["mcpServers"]["fs"]["command"] == "npx"

    declined = runner.invoke(cli.app, ["install"], input="n\n")
    assert declined.exit_code == 1

    done = runner.invoke(cli.app, ["install", "--include-http", "--client", "cursor"], input="y\n")
    assert done.exit_code == 0, done.output
    assert "cursor (user)  ~/.cursor/mcp.json" in done.output
    assert "updated ~/.cursor/mcp.json" in done.output
    assert "keep `mcphawk up` running" in done.output
    config = json.loads(fake_home.read_text())
    assert config["mcpServers"]["fs"]["command"] == "/bin/mcphawk"
    assert config["mcpServers"]["web"]["url"] == "http://127.0.0.1:8484/p/web"

    status = runner.invoke(cli.app, ["status"])
    assert "routed     2 server(s)" in status.output

    nothing = runner.invoke(cli.app, ["install", "-y"])
    assert "Nothing to change" in nothing.output

    undone = runner.invoke(cli.app, ["uninstall", "-y"])
    assert undone.exit_code == 0, undone.output
    assert json.loads(fake_home.read_text())["mcpServers"]["web"]["url"] == (
        "http://localhost:3000/mcp")


def test_install_rejects_unknown_client_and_empty_home(fake_home, tmp_path, monkeypatch):
    bad = runner.invoke(cli.app, ["install", "--client", "emacs"])
    assert bad.exit_code == 2
    monkeypatch.setattr(cli.installer.Path, "home", lambda: tmp_path / "empty")
    empty = runner.invoke(cli.app, ["install", "--dry-run"])
    assert "No MCP client configurations found" in empty.output


def test_status_clear_and_sniff_validation(recorder):
    legacy_session(recorder)
    status = runner.invoke(cli.app, ["status"])
    assert "1 sessions, 5 calls, 2 errors" in status.output
    assert runner.invoke(cli.app, ["clear"], input="n\n").exit_code == 1
    assert runner.invoke(cli.app, ["clear", "-y"]).output.strip() == "cleared"
    assert "0 sessions" in runner.invoke(cli.app, ["status"]).output
    assert runner.invoke(cli.app, ["sniff"]).exit_code == 2


def test_sniff_permission_error(monkeypatch):
    def denied(*a, **kw):
        raise PermissionError

    monkeypatch.setattr("mcphawk.capture.sniff.run_sniffer", denied)
    result = runner.invoke(cli.app, ["sniff", "-a"])
    assert result.exit_code == 1
    assert "needs root" in result.output


def test_mcp_command(monkeypatch):
    ran = []

    async def fake_stdio(self):
        ran.append("stdio")

    from mcp.server.mcpserver import MCPServer

    monkeypatch.setattr(MCPServer, "run_stdio_async", fake_stdio)
    assert runner.invoke(cli.app, ["mcp"]).exit_code == 0
    assert ran == ["stdio"]
    assert runner.invoke(cli.app, ["mcp", "--transport", "carrier-pigeon"]).exit_code == 2


def test_sniff_filter_builder():
    assert cli._sniff_filter(None, "tcp port 1", True) == "tcp port 1"
    assert cli._sniff_filter([1], None, False) == "tcp port 1"
    assert cli._sniff_filter(None, None, True) == "tcp"
    assert cli._sniff_filter(None, None, False) is None


def test_web_alias_still_starts_the_ui(monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    result = runner.invoke(cli.app, ["web", "--web-port", "9100"])
    assert result.exit_code == 0
    assert calls[0]["port"] == 9100
    assert "now `mcphawk up`" in result.output
