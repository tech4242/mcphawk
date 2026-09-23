"""SQLite schema and connections.

Several processes write at once (one ``mcphawk wrap`` per wrapped server, a
proxy, a sniffer) while the web UI and MCP server read, so the database runs
in WAL mode with a generous busy timeout.
"""

import sqlite3
from pathlib import Path

from mcphawk.paths import db_path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    client_key       TEXT,
    name             TEXT,
    capture          TEXT NOT NULL,
    transport        TEXT NOT NULL,
    target           TEXT,
    client_app       TEXT,
    client_name      TEXT,
    client_version   TEXT,
    server_name      TEXT,
    server_version   TEXT,
    protocol_version TEXT,
    era              TEXT,
    pid              INTEGER,
    client_pid       INTEGER,
    started_at       REAL NOT NULL,
    last_seen_at     REAL NOT NULL,
    ended_at         REAL,
    hidden           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_key, started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);

CREATE TABLE IF NOT EXISTS exchanges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    initiator       TEXT NOT NULL,
    method          TEXT NOT NULL,
    target          TEXT,
    rpc_id          TEXT,
    request_msg_id  INTEGER,
    response_msg_id INTEGER,
    started_at      REAL NOT NULL,
    ended_at        REAL,
    duration_ms     REAL,
    status          TEXT NOT NULL DEFAULT 'pending',
    error_code      INTEGER,
    error_message   TEXT,
    request_tokens  INTEGER NOT NULL DEFAULT 0,
    response_tokens INTEGER NOT NULL DEFAULT 0,
    parent_id       INTEGER,
    chain_root_id   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_exchanges_session ON exchanges(session_id, started_at);
CREATE INDEX IF NOT EXISTS idx_exchanges_status ON exchanges(status);
CREATE INDEX IF NOT EXISTS idx_exchanges_method ON exchanges(method, target);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    exchange_id INTEGER,
    ts          REAL NOT NULL,
    direction   TEXT NOT NULL CHECK(direction IN ('c2s', 's2c')),
    kind        TEXT NOT NULL,
    method      TEXT,
    rpc_id      TEXT,
    size        INTEGER NOT NULL,
    tokens      INTEGER NOT NULL,
    body        TEXT NOT NULL,
    headers     TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_exchange ON messages(exchange_id);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open (and if needed create) the capture database."""
    path = Path(path) if path else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()
    return conn
