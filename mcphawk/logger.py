import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Set up logger for this module
logger = logging.getLogger(__name__)

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
    logger.debug(f"init_db: Using DB_PATH = {DB_PATH}")
    if not DB_PATH or not str(DB_PATH).strip():
        raise ValueError("DB_PATH is not set or is empty")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            log_id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            src_ip TEXT,
            dst_ip TEXT,
            src_port INTEGER,
            dst_port INTEGER,
            direction TEXT CHECK(direction IN ('incoming', 'outgoing', 'unknown')),
            message TEXT,
            traffic_type TEXT,
            metadata TEXT
        )
        """
    )

    # Add traffic_type and metadata columns to existing tables
    cur.execute("PRAGMA table_info(logs)")
    columns = [col[1] for col in cur.fetchall()]
    if "traffic_type" not in columns:
        cur.execute("ALTER TABLE logs ADD COLUMN traffic_type TEXT")
    if "metadata" not in columns:
        cur.execute("ALTER TABLE logs ADD COLUMN metadata TEXT")
    conn.commit()
    conn.close()


def log_message(entry: dict[str, Any]) -> None:
    """
    Insert a new log entry.

    Args:
        entry (Dict[str, Any]): Must contain MCPMessageLog fields:
            log_id (str) - UUID for the log entry
            timestamp (datetime) - If missing, current time is used
            src_ip (str)
            dst_ip (str)
            src_port (int)
            dst_port (int)
            direction (str): 'incoming', 'outgoing', or 'unknown'
            message (str)
            traffic_type (str): 'TCP', 'WS', or 'N/A' (optional, defaults to 'N/A')
            metadata (str): JSON string with additional metadata (optional)
    """
    timestamp = entry.get("timestamp", datetime.now(tz=timezone.utc))
    log_id = entry.get("log_id")
    if not log_id:
        raise ValueError("log_id is required")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO logs (log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, traffic_type, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log_id,
            timestamp.isoformat(),
            entry.get("src_ip"),
            entry.get("dst_ip"),
            entry.get("src_port"),
            entry.get("dst_port"),
            entry.get("direction", "unknown"),
            entry.get("message"),
            entry.get("traffic_type", "N/A"),
            entry.get("metadata"),
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
    logger.debug(f"fetch_logs: Using DB_PATH = {current_path}, exists = {current_path.exists() if current_path else False}")

    # If the database doesn't exist, it might have been deleted or path changed
    if not current_path.exists():
        logger.warning(f"Database file not found at {current_path}")
        return []

    conn = sqlite3.connect(current_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, traffic_type, metadata
        FROM logs
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "log_id": row["log_id"],
            "timestamp": datetime.fromisoformat(row["timestamp"]),
            "src_ip": row["src_ip"],
            "dst_ip": row["dst_ip"],
            "src_port": row["src_port"],
            "dst_port": row["dst_port"],
            "direction": row["direction"],
            "message": row["message"],
            "traffic_type": row["traffic_type"] if row["traffic_type"] is not None else "N/A",
            "metadata": row["metadata"],
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
        logger.debug(f"set_db_path: Changed DB_PATH to {DB_PATH}")
    else:
        logger.warning(f"set_db_path: Ignoring empty path, keeping DB_PATH as {DB_PATH}")


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


def get_log_by_id(log_id: str) -> dict[str, Any] | None:
    """
    Fetch a specific log entry by ID.

    Args:
        log_id (str): The UUID of the log entry to retrieve.

    Returns:
        Dictionary matching MCPMessageLog format or None if not found.
    """
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    if not current_path.exists():
        return None

    conn = sqlite3.connect(current_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, traffic_type, metadata
        FROM logs
        WHERE log_id = ?
        """,
        (log_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "log_id": row["log_id"],
        "timestamp": datetime.fromisoformat(row["timestamp"]),
        "src_ip": row["src_ip"],
        "dst_ip": row["dst_ip"],
        "src_port": row["src_port"],
        "dst_port": row["dst_port"],
        "direction": row["direction"],
        "message": row["message"],
        "traffic_type": row["traffic_type"] if row["traffic_type"] is not None else "N/A",
        "metadata": row["metadata"],
    }
