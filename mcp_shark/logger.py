"""
Logger module for MCP-Shark.

Handles SQLite database operations for storing and retrieving logs.
Automatically initializes or upgrades the database schema.
"""

import os
import sqlite3
from typing import List, Dict, Any

# Default database path (backward compatible alias for tests)
DB_PATH = os.getenv("MCP_SHARK_DB", "mcp_shark_logs.db")
DB_FILE = DB_PATH  # ✅ Compatibility for old tests expecting DB_FILE


def set_db_path(path: str) -> None:
    """
    Set a custom database path (useful for testing).
    """
    global DB_PATH, DB_FILE
    DB_PATH = path
    DB_FILE = path


def init_db() -> None:
    """
    Initialize or upgrade the SQLite database to ensure it has the correct schema.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ✅ Drop and re-create table if columns are missing
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            src_ip TEXT,
            src_port INTEGER,
            dst_ip TEXT,
            dst_port INTEGER,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # ✅ Check if `src_port` exists (upgrade old DBs)
    cur.execute("PRAGMA table_info(logs)")
    columns = [row[1] for row in cur.fetchall()]
    if "src_port" not in columns:
        cur.execute("DROP TABLE IF EXISTS logs")
        cur.execute(
            """
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_ip TEXT,
                src_port INTEGER,
                dst_ip TEXT,
                dst_port INTEGER,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    conn.commit()
    conn.close()


def log_message(log_entry: Dict[str, Any]) -> None:
    """
    Insert a log entry into the database.

    Args:
        log_entry (dict): Keys: src_ip, src_port, dst_ip, dst_port, message
    """
    init_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (src_ip, src_port, dst_ip, dst_port, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            log_entry.get("src_ip", ""),
            log_entry.get("src_port", 0),
            log_entry.get("dst_ip", ""),
            log_entry.get("dst_port", 0),
            log_entry.get("message", ""),
        ),
    )
    conn.commit()
    conn.close()


def fetch_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch the latest logs from the database.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, src_ip, src_port, dst_ip, dst_port, message, timestamp
        FROM logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def clear_logs() -> None:
    """
    Clear all logs from the database.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM logs")
    conn.commit()
    conn.close()
