"""Where MCP clients keep their server configuration, and in what shape."""

import json
import os
import platform
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLAUDE_DESKTOP = "claude-desktop"
CLAUDE_CODE = "claude-code"
CURSOR = "cursor"
VSCODE = "vscode"
ALL_CLIENTS = (CLAUDE_DESKTOP, CLAUDE_CODE, CURSOR, VSCODE)


@dataclass(frozen=True)
class ServerTable:
    """One ``{name: server}`` mapping inside a config file."""

    client: str
    scope: str
    path: Path
    keys: tuple[str, ...]  # JSON path to the mapping

    def label(self) -> str:
        return f"{self.client} ({self.scope})"


def _app_support(home: Path) -> Path:
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Application Support"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    return Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))


def config_files(client: str, home: Path, project: Path | None) -> list[tuple[str, Path]]:
    """(scope, path) pairs a client reads, whether or not they exist."""
    support = _app_support(home)
    if client == CLAUDE_DESKTOP:
        return [("user", support / "Claude" / "claude_desktop_config.json")]
    if client == CLAUDE_CODE:
        files = [("user", home / ".claude.json")]
        if project:
            files.append(("project", project / ".mcp.json"))
        return files
    if client == CURSOR:
        files = [("user", home / ".cursor" / "mcp.json")]
        if project:
            files.append(("project", project / ".cursor" / "mcp.json"))
        return files
    if client == VSCODE:
        files = [("user", support / "Code" / "User" / "mcp.json")]
        if project:
            files.append(("project", project / ".vscode" / "mcp.json"))
        return files
    raise ValueError(f"unknown client {client!r}")


_COMMENTS = re.compile(
    r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/', re.MULTILINE)
_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(\s*[}\]])')


def loads_jsonc(text: str) -> Any:
    """Parse JSON with comments and trailing commas (VS Code's mcp.json)."""
    def strip_comment(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token.startswith('"') else ""

    def strip_comma(match: re.Match[str]) -> str:
        return match.group(1) if match.group(1) is not None else match.group(0)

    text = _COMMENTS.sub(strip_comment, text)
    text = _TRAILING_COMMA.sub(strip_comma, text)
    return json.loads(text) if text.strip() else {}


def has_comments(text: str) -> bool:
    return any(not m.group(0).startswith('"') for m in _COMMENTS.finditer(text))


def server_tables(client: str, data: dict[str, Any], scope: str,
                  path: Path) -> Iterator[ServerTable]:
    key = "servers" if client == VSCODE else "mcpServers"
    if isinstance(data.get(key), dict):
        yield ServerTable(client, scope, path, (key,))
    if client == CLAUDE_CODE and scope == "user":
        for project, settings in (data.get("projects") or {}).items():
            if isinstance(settings, dict) and isinstance(settings.get("mcpServers"), dict):
                yield ServerTable(client, f"local:{project}", path,
                                  ("projects", project, "mcpServers"))


def resolve(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    for key in keys:
        data = data[key]
    return data
