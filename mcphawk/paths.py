"""Filesystem locations used by MCPHawk."""

import os
from pathlib import Path


def data_dir() -> Path:
    """Directory holding the database, backups and proxy registry.

    Overridable with ``MCPHAWK_HOME``; defaults to ``~/.mcphawk``.
    """
    override = os.environ.get("MCPHAWK_HOME")
    path = Path(override).expanduser() if override else Path.home() / ".mcphawk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Path of the capture database (``MCPHAWK_DB`` overrides it)."""
    override = os.environ.get("MCPHAWK_DB")
    if override:
        path = Path(override).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return data_dir() / "mcphawk.db"
