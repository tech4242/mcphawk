"""Which MCP client launched us? Used to group stdio sessions into runs."""

import os
from dataclasses import dataclass

import psutil

# Launchers that can sit between an MCP client and ``mcphawk wrap``. Node is
# deliberately absent: Node-based clients (Claude Code, VS Code) *are* node.
_LAUNCHERS = frozenset({
    "uv", "uvx", "pipx", "python", "python3", "sh", "bash", "zsh", "dash", "fish",
    "env", "cmd.exe", "powershell.exe", "pwsh", "mcphawk", "timeout", "nice",
    "caffeinate",
})


@dataclass
class ClientProcess:
    pid: int
    name: str
    run_key: str


def _is_launcher(proc: psutil.Process) -> bool:
    name = proc.name().lower()
    stem = name.removesuffix(".exe")
    if name in _LAUNCHERS or stem in _LAUNCHERS or stem.startswith("python3."):
        return True
    try:
        cmdline = " ".join(proc.cmdline()).lower()
    except (psutil.Error, OSError):
        return False
    return "mcphawk" in cmdline and "wrap" in cmdline


def find_client(start_pid: int | None = None, max_depth: int = 8) -> ClientProcess | None:
    """Walk up from our parent to the first process that is not a launcher.

    If every ancestor looks like a launcher we fall back to the direct parent.
    """
    try:
        proc = psutil.Process(start_pid or os.getppid())
        first = proc
        for _ in range(max_depth):
            if not _is_launcher(proc):
                break
            parent = proc.parent()
            if parent is None or parent.pid <= 1:
                proc = first
                break
            proc = parent
        else:
            proc = first
        return ClientProcess(
            pid=proc.pid,
            name=proc.name(),
            run_key=f"pid:{proc.pid}:{int(proc.create_time())}",
        )
    except (psutil.Error, OSError):
        return None
