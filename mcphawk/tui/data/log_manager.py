"""Log manager for TUI - polls SQLite for updates."""

import contextlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mcphawk.logger import get_db_connection
from mcphawk.utils import get_message_type

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A single log entry."""

    id: int
    timestamp: datetime
    src_ip: Optional[str]
    src_port: Optional[int]
    dst_ip: Optional[str]
    dst_port: Optional[int]
    direction: str
    message: str
    transport_type: str
    metadata: dict
    pid: Optional[int]

    @property
    def message_type(self) -> str:
        """Get the JSON-RPC message type."""
        return get_message_type(self.message)

    @property
    def method(self) -> Optional[str]:
        """Extract method from JSON-RPC message."""
        try:
            data = json.loads(self.message)
            return data.get("method")
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def message_id(self) -> Optional[str]:
        """Extract id from JSON-RPC message."""
        try:
            data = json.loads(self.message)
            return str(data.get("id")) if data.get("id") is not None else None
        except (json.JSONDecodeError, TypeError):
            return None

    @property
    def server_name(self) -> Optional[str]:
        """Get server name from metadata."""
        return self.metadata.get("server_name")


@dataclass
class LogStats:
    """Statistics about captured logs."""

    total: int = 0
    requests: int = 0
    responses: int = 0
    notifications: int = 0
    errors: int = 0


class LogManager:
    """Manages log data with polling from SQLite."""

    def __init__(self, max_entries: int = 1000):
        """Initialize the log manager.

        Args:
            max_entries: Maximum entries to keep in memory.
        """
        self.max_entries = max_entries
        self.entries: list[LogEntry] = []
        self.last_id: int = 0
        self.stats = LogStats()

        # Filter state
        self.type_filter: Optional[str] = None  # request, response, notification, error
        self.transport_filter: Optional[str] = None  # streamable_http, http_sse, stdio
        self.server_filter: Optional[str] = None
        self.search_query: str = ""

    def poll_for_updates(self) -> list[LogEntry]:
        """Poll database for new entries since last check.

        Returns:
            List of new entries.
        """
        new_entries = []

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT log_id, timestamp, src_ip, src_port, dst_ip, dst_port,
                       direction, message, transport_type, metadata, pid
                FROM logs
                WHERE log_id > ?
                ORDER BY log_id ASC
                LIMIT 100
                """,
                (self.last_id,),
            )

            for row in cur.fetchall():
                entry = self._row_to_entry(row)
                new_entries.append(entry)
                self.last_id = entry.id

        # Add to entries list and update stats
        for entry in new_entries:
            self._add_entry(entry)

        return new_entries

    def _row_to_entry(self, row) -> LogEntry:
        """Convert a database row to a LogEntry."""
        metadata = {}
        if row["metadata"]:
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(row["metadata"])

        return LogEntry(
            id=row["log_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            src_ip=row["src_ip"],
            src_port=row["src_port"],
            dst_ip=row["dst_ip"],
            dst_port=row["dst_port"],
            direction=row["direction"],
            message=row["message"],
            transport_type=row["transport_type"] or "unknown",
            metadata=metadata,
            pid=row["pid"],
        )

    def _add_entry(self, entry: LogEntry) -> None:
        """Add an entry and update stats."""
        self.entries.append(entry)

        # Update stats
        self.stats.total += 1
        msg_type = entry.message_type
        if msg_type == "request":
            self.stats.requests += 1
        elif msg_type == "response":
            self.stats.responses += 1
        elif msg_type == "notification":
            self.stats.notifications += 1
        elif msg_type == "error":
            self.stats.errors += 1

        # Trim if over max
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def get_filtered_entries(self) -> list[LogEntry]:
        """Get entries matching current filters."""
        result = []

        for entry in self.entries:
            # Type filter
            if self.type_filter and entry.message_type != self.type_filter:
                continue

            # Transport filter
            if self.transport_filter and entry.transport_type != self.transport_filter:
                continue

            # Server filter
            if self.server_filter and entry.server_name != self.server_filter:
                continue

            # Search query
            if self.search_query:
                query = self.search_query.lower()
                in_message = query in entry.message.lower()
                in_method = entry.method and query in entry.method.lower()
                if not in_message and not in_method:
                    continue

            result.append(entry)

        return result

    def get_unique_servers(self) -> list[str]:
        """Get list of unique server names."""
        servers = set()
        for entry in self.entries:
            if entry.server_name:
                servers.add(entry.server_name)
        return sorted(servers)

    def get_unique_transports(self) -> list[str]:
        """Get list of unique transport types."""
        transports = set()
        for entry in self.entries:
            if entry.transport_type:
                transports.add(entry.transport_type)
        return sorted(transports)

    def clear(self) -> None:
        """Clear all entries and reset stats."""
        self.entries.clear()
        self.last_id = 0
        self.stats = LogStats()
