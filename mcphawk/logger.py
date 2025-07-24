import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Database file (shared with tests)
DB_FILE = "mcphawk_logs.db"
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / DB_FILE
DB_PATH = _DEFAULT_DB_PATH

# Module initialization flag
_db_initialized = False


def init_db() -> None:
    """
    Initialize the SQLite database and ensure the logs table exists.
    """
    print(f"[DEBUG] init_db: Using DB_PATH = {DB_PATH}")
    if not DB_PATH or not str(DB_PATH).strip():
        raise ValueError("DB_PATH is not set or is empty")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            src_ip TEXT,
            dst_ip TEXT,
            src_port INTEGER,
            dst_port INTEGER,
            direction TEXT CHECK(direction IN ('incoming', 'outgoing', 'unknown')),
            message TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_message(entry: dict[str, Any]) -> None:
    """
    Insert a new log entry.

    Args:
        entry (Dict[str, Any]): Must contain MCPMessageLog fields:
            timestamp (datetime) - If missing, current time is used
            src_ip (str)
            dst_ip (str)
            src_port (int)
            dst_port (int)
            direction (str): 'incoming', 'outgoing', or 'unknown'
            message (str)
    """
    timestamp = entry.get("timestamp", datetime.now(tz=UTC))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (timestamp, src_ip, dst_ip, src_port, dst_port, direction, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp.isoformat(),
            entry.get("src_ip"),
            entry.get("dst_ip"),
            entry.get("src_port"),
            entry.get("dst_port"),
            entry.get("direction", "unknown"),
            entry.get("message"),
        ),
    )
    conn.commit()
    conn.close()


def fetch_logs(limit: int = 100) -> list[dict[str, Any]]:
    """
    Fetch the latest logs.

    Args:
        limit (int): Max number of logs to retrieve.

    Returns:
        List of dictionaries matching MCPMessageLog format.
    """
    # Ensure we're using the correct path
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    print(f"[DEBUG] fetch_logs: Using DB_PATH = {current_path}, exists = {current_path.exists() if current_path else False}")

    # If the database doesn't exist, it might have been deleted or path changed
    if not current_path.exists():
        print(f"[WARNING] Database file not found at {current_path}")
        return []

    conn = sqlite3.connect(current_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT timestamp, src_ip, dst_ip, src_port, dst_port, direction, message
        FROM logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "timestamp": datetime.fromisoformat(row["timestamp"]),
            "src_ip": row["src_ip"],
            "dst_ip": row["dst_ip"],
            "src_port": row["src_port"],
            "dst_port": row["dst_port"],
            "direction": row["direction"],
            "message": row["message"],
        }
        for row in rows
    ]


# Add this near the top of logger.py (after DB_PATH definition)
def set_db_path(path: str) -> None:
    """
    Override the default DB path (used in tests).
    """
    global DB_PATH, _db_initialized
    if path:
        DB_PATH = Path(path)
        _db_initialized = False  # Reset initialization flag when path changes
        print(f"[DEBUG] set_db_path: Changed DB_PATH to {DB_PATH}")
    else:
        print(f"[WARNING] set_db_path: Ignoring empty path, keeping DB_PATH as {DB_PATH}")


def clear_logs() -> None:
    """
    Clear all logs from the database.
    Mainly used in tests.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM logs;")
    conn.commit()
    conn.close()
