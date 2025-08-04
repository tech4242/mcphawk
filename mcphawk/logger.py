import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
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


@contextmanager
def get_db_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for SQLite database connections.

    Args:
        db_path: Optional path to database. Uses DB_PATH if not provided.

    Yields:
        sqlite3.Connection: Database connection with row_factory set.

    Example:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM logs")
    """
    path = db_path or DB_PATH
    if not path:
        raise ValueError("No database path provided")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """
    Initialize the SQLite database and ensure the logs table exists.
    """
    logger.debug(f"init_db: Using DB_PATH = {DB_PATH}")
    if not DB_PATH or not str(DB_PATH).strip():
        raise ValueError("DB_PATH is not set or is empty")

    with get_db_connection() as conn:
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
                transport_type TEXT,
                metadata TEXT,
                pid INTEGER
            )
            """
        )
        conn.commit()


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
            transport_type (str): 'streamable_http', 'http_sse', 'stdio', or 'unknown' (optional, defaults to 'unknown')
            metadata (str): JSON string with additional metadata (optional)
            pid (int): Process ID for stdio transport (optional)
    """
    timestamp = entry.get("timestamp", datetime.now(tz=timezone.utc))
    log_id = entry.get("log_id")
    if not log_id:
        raise ValueError("log_id is required")

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO logs (log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, transport_type, metadata, pid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                entry.get("transport_type", "unknown"),
                entry.get("metadata"),
                entry.get("pid"),
            ),
        )
        conn.commit()


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

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, transport_type, metadata, pid
            FROM logs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()

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
            "transport_type": row["transport_type"] if row["transport_type"] is not None else "unknown",
            "metadata": row["metadata"],
            "pid": row["pid"],
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
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM logs;")
        conn.commit()


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

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, transport_type, metadata, pid
            FROM logs
            WHERE log_id = ?
            """,
            (log_id,),
        )
        row = cur.fetchone()

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
        "transport_type": row["transport_type"] if row["transport_type"] is not None else "unknown",
        "metadata": row["metadata"],
        "pid": row["pid"],
    }


def fetch_logs_with_offset(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """
    Fetch logs with limit and offset for pagination.

    Args:
        limit: Maximum number of logs to return
        offset: Number of logs to skip

    Returns:
        List of dictionaries matching MCPMessageLog format.
    """
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    if not current_path.exists():
        return []

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT log_id, timestamp, src_ip, dst_ip, src_port, dst_port, direction, message, transport_type, metadata, pid
            FROM logs
            ORDER BY log_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = cur.fetchall()

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
            "transport_type": row["transport_type"] if row["transport_type"] is not None else "unknown",
            "metadata": row["metadata"],
            "pid": row["pid"],
        }
        for row in rows
    ]


def search_logs(search_term: str = "", message_type: str | None = None,
                transport_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """
    Search logs by various criteria.

    Args:
        search_term: Text to search for in messages
        message_type: Filter by JSON-RPC message type (request, response, notification)
        transport_type: Filter by transport type (streamable_http, http_sse, stdio, unknown)
        limit: Maximum number of results

    Returns:
        List of matching log entries.
    """
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    if not current_path.exists():
        return []

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()

        query = "SELECT * FROM logs WHERE 1=1"
        params = []

        if search_term:
            query += " AND message LIKE ?"
            params.append(f"%{search_term}%")

        if transport_type:
            query += " AND transport_type = ?"
            params.append(transport_type)

        query += " ORDER BY log_id DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()

    # Filter by message type if specified
    results = []
    for row in rows:
        log_dict = {
            "log_id": row["log_id"],
            "timestamp": datetime.fromisoformat(row["timestamp"]),
            "src_ip": row["src_ip"],
            "dst_ip": row["dst_ip"],
            "src_port": row["src_port"],
            "dst_port": row["dst_port"],
            "direction": row["direction"],
            "message": row["message"],
            "transport_type": row["transport_type"] if row["transport_type"] is not None else "unknown",
            "metadata": row["metadata"],
            "pid": row["pid"],
        }

        # If message_type filter is specified, check it
        if message_type:
            from .utils import get_message_type
            if get_message_type(row["message"]) != message_type:
                continue

        results.append(log_dict)

    return results


def get_traffic_stats() -> dict[str, Any]:
    """
    Get statistics about captured traffic.

    Returns:
        Dictionary with traffic statistics.
    """
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    if not current_path.exists():
        return {
            "total_logs": 0,
            "requests": 0,
            "responses": 0,
            "notifications": 0,
            "errors": 0,
            "by_transport_type": {}
        }

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()

        # Get all messages for analysis
        cur.execute("SELECT message, transport_type FROM logs")
        logs = cur.fetchall()

    stats = {
        "total_logs": len(logs),
        "requests": 0,
        "responses": 0,
        "notifications": 0,
        "errors": 0,
        "by_transport_type": {}
    }

    from .utils import get_message_type

    for message, transport_type in logs:
        # Count by message type
        msg_type = get_message_type(message)
        if msg_type == "request":
            stats["requests"] += 1
        elif msg_type == "response":
            stats["responses"] += 1
        elif msg_type == "notification":
            stats["notifications"] += 1

        # Check for errors
        try:
            import json
            msg_data = json.loads(message)
            if "error" in msg_data:
                stats["errors"] += 1
        except Exception:
            pass

        # Count by transport type
        if transport_type:
            stats["by_transport_type"][transport_type] = stats["by_transport_type"].get(transport_type, 0) + 1

    return stats


def get_unique_methods() -> list[str]:
    """
    Get all unique JSON-RPC methods from captured traffic.

    Returns:
        Sorted list of unique method names.
    """
    current_path = DB_PATH if DB_PATH else _DEFAULT_DB_PATH
    if not current_path.exists():
        return []

    with get_db_connection(current_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT message FROM logs")
        logs = cur.fetchall()

    methods = set()
    for (message,) in logs:
        try:
            import json
            msg_data = json.loads(message)
            if "method" in msg_data:
                methods.add(msg_data["method"])
        except Exception:
            pass

    return sorted(methods)
