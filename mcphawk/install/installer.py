"""``mcphawk install`` / ``uninstall``: route client configs through MCPHawk.

stdio servers get ``mcphawk wrap --`` put in front of their command. HTTP
servers are pointed at the MCPHawk proxy (``mcphawk up`` must then be
running). Every file is backed up before it is written, and uninstall undoes
the change structurally, so edits made in between survive.
"""

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mcphawk.install import clients as cl
from mcphawk.paths import data_dir

DEFAULT_PORT = 8484
WRAP_MARKER = "wrap"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"})

WRAP = "wrap"
PROXY = "proxy"
UNWRAP = "unwrap"
UNPROXY = "unproxy"
SKIP = "skip"


@dataclass
class Change:
    table: cl.ServerTable
    server: str
    action: str
    reason: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] | None = None


# -- proxy registry -------------------------------------------------------

def registry_path() -> Path:
    return data_dir() / "proxies.json"


def load_registry() -> dict[str, str]:
    """Proxy name -> upstream URL, as used by ``mcphawk up``."""
    try:
        data = json.loads(registry_path().read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def save_registry(registry: dict[str, str]) -> None:
    registry_path().write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")


# -- command resolution ---------------------------------------------------

def mcphawk_command() -> list[str]:
    """How a GUI app (without the user's shell PATH) should launch mcphawk."""
    if "/uv/archive-" in sys.executable or "/.cache/uv/" in sys.executable:
        uvx = shutil.which("uvx")
        return [uvx or "uvx", "mcphawk"]
    script = Path(sys.argv[0])
    if script.name in ("mcphawk", "mcphawk.exe") and script.exists():
        return [str(script.resolve())]
    found = shutil.which("mcphawk")
    return [found] if found else [sys.executable, "-m", "mcphawk"]


def _is_mcphawk(command: str | None, args: list[str]) -> bool:
    if not command:
        return False
    tokens = [os.path.basename(command), *args[:2]]
    return any(t in ("mcphawk", "mcphawk.exe") for t in tokens) or (
        args[:2] == ["-m", "mcphawk"])


def wrapped_original(server: dict[str, Any]) -> tuple[str, list[str]] | None:
    """The original command of a wrapped stdio server, or None."""
    args = [str(a) for a in server.get("args") or []]
    if not _is_mcphawk(server.get("command"), args) or WRAP_MARKER not in args:
        return None
    after_wrap = args[args.index(WRAP_MARKER) + 1:]
    if "--" in after_wrap:
        rest = after_wrap[after_wrap.index("--") + 1:]
    else:
        # v0.x syntax: `mcphawk wrap [--debug] <command...>`
        rest = [a for i, a in enumerate(after_wrap)
                if not (a in ("--debug", "-d") and i == 0)]
    return (rest[0], rest[1:]) if rest else None


def _url_key(server: dict[str, Any]) -> str | None:
    for key in ("url", "serverUrl"):
        if isinstance(server.get(key), str):
            return key
    return None


def proxy_url(port: int, name: str) -> str:
    return f"http://127.0.0.1:{port}/p/{name}"


def _proxied_name(url: str, port: int) -> str | None:
    prefix = f"http://127.0.0.1:{port}/p/"
    return url[len(prefix):].split("/")[0] if url.startswith(prefix) else None


# -- planning -------------------------------------------------------------

def _plan_install(table: cl.ServerTable, name: str, server: dict[str, Any], *,
                  command: list[str], include_http: bool, force_http: bool, port: int,
                  registry: dict[str, str]) -> Change:
    change = Change(table, name, SKIP, before=dict(server))
    url_key = _url_key(server)
    if server.get("disabled"):
        change.reason = "disabled"
    elif url_key:
        url = server[url_key]
        if _proxied_name(url, port):
            change.reason = "already proxied"
        elif not include_http:
            change.reason = "HTTP server (use --include-http)"
        elif (not force_http and urlsplit(url).hostname not in LOCAL_HOSTS
              and not server.get("headers")):
            change.reason = "remote server without static headers, probably OAuth (--force-http)"
        else:
            proxy_name = _unique_name(name, url, registry)
            registry[proxy_name] = url
            change.action = PROXY
            change.after = {**server, url_key: proxy_url(port, proxy_name)}
    elif isinstance(server.get("command"), str):
        args = [str(a) for a in server.get("args") or []]
        if wrapped_original(server):
            change.reason = "already wrapped"
        elif _is_mcphawk(server["command"], args):
            change.reason = "this is MCPHawk itself"
        else:
            change.action = WRAP
            change.after = {
                **server,
                "command": command[0],
                "args": [*command[1:], WRAP_MARKER, "--name", name, "--",
                         server["command"], *args],
            }
    else:
        change.reason = "unrecognised server entry"
    return change


def _unique_name(name: str, url: str, registry: dict[str, str]) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name) or "server"
    candidate, n = safe, 2
    while registry.get(candidate) not in (None, url):
        candidate, n = f"{safe}-{n}", n + 1
    return candidate


def _plan_uninstall(table: cl.ServerTable, name: str, server: dict[str, Any], *,
                    port: int, registry: dict[str, str]) -> Change:
    change = Change(table, name, SKIP, before=dict(server))
    original = wrapped_original(server)
    url_key = _url_key(server)
    if original:
        command, args = original
        change.action = UNWRAP
        change.after = {**server, "command": command, "args": args}
    elif url_key and _proxied_name(server[url_key], port):
        proxy_name = _proxied_name(server[url_key], port)
        if proxy_name in registry:
            change.action = UNPROXY
            change.after = {**server, url_key: registry[proxy_name]}
        else:
            change.reason = f"proxy {proxy_name!r} missing from registry"
    else:
        change.reason = "not routed through MCPHawk"
    return change


def _read(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        text = path.read_text()
    except OSError:
        return None, ""
    try:
        data = cl.loads_jsonc(text)
    except json.JSONDecodeError:
        return None, text
    return (data if isinstance(data, dict) else None), text


def plan(
    *,
    uninstall: bool = False,
    clients: tuple[str, ...] = cl.ALL_CLIENTS,
    home: Path | None = None,
    project: Path | None = None,
    include_http: bool = False,
    force_http: bool = False,
    port: int = DEFAULT_PORT,
    command: list[str] | None = None,
    registry: dict[str, str] | None = None,
) -> list[Change]:
    home = home or Path.home()
    command = command or mcphawk_command()
    registry = registry if registry is not None else load_registry()
    changes = []
    for client in clients:
        for scope, path in cl.config_files(client, home, project):
            data, _ = _read(path)
            if data is None:
                continue
            for table in cl.server_tables(client, data, scope, path):
                for name, server in cl.resolve(data, table.keys).items():
                    if not isinstance(server, dict):
                        continue
                    if uninstall:
                        changes.append(_plan_uninstall(
                            table, name, server, port=port, registry=registry))
                    else:
                        changes.append(_plan_install(
                            table, name, server, command=command,
                            include_http=include_http or force_http,
                            force_http=force_http, port=port, registry=registry))
    return changes


# -- applying -------------------------------------------------------------

def backup(path: Path) -> Path:
    folder = data_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    parent = path.parent.name.strip(".") or "root"
    target = folder / f"{stamp}-{parent}-{path.name}"
    n = 1
    while target.exists():
        target = folder / f"{stamp}-{parent}-{n}-{path.name}"
        n += 1
    shutil.copy2(path, target)
    return target


def apply(changes: list[Change], registry: dict[str, str] | None = None) -> list[str]:
    """Write the planned changes. Returns human-readable notes."""
    notes = []
    effective = [c for c in changes if c.after is not None]
    by_file: dict[Path, list[Change]] = {}
    for change in effective:
        by_file.setdefault(change.table.path, []).append(change)
    for path, file_changes in by_file.items():
        data, text = _read(path)
        if data is None:
            notes.append(f"skipped {path}: could not parse it")
            continue
        if cl.has_comments(text):
            notes.append(f"{path}: comments are not preserved when rewriting")
        saved = backup(path)
        for change in file_changes:
            cl.resolve(data, change.table.keys)[change.server] = change.after
        tmp = path.with_suffix(path.suffix + ".mcphawk-tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
        notes.append(f"updated {path} (backup: {saved})")
    if registry is not None and any(c.action == PROXY for c in effective):
        save_registry(registry)
    return notes
