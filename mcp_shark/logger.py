import sqlite3
from .models import MCPMessageLog

DB_FILE = "mcp_sniffer_logs.db"


def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            src_ip TEXT,
            dst_ip TEXT,
            src_port INTEGER,
            dst_port INTEGER,
            direction TEXT,
            message TEXT
        )
        """)
    conn.close()


def log_message(entry: MCPMessageLog) -> None:
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute("""
        INSERT INTO logs (timestamp, src_ip, dst_ip, src_port, dst_port, direction, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["timestamp"].isoformat(),
            entry["src_ip"],
            entry["dst_ip"],
            entry["src_port"],
            entry["dst_port"],
            entry["direction"],
            entry["message"]
        ))
    conn.close()
