"""Read side of the capture database.

The web UI and the MCPHawk MCP server are thin views over this module; any
question either of them can answer should be answerable here first.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any

import psutil

from mcphawk.store.db import connect

HUNG_AFTER_S = 30.0
IDLE_AFTER_S = 600.0

_SESSION_COLUMNS = (
    "id, run_key, name, capture, transport, target, client_app, client_name, "
    "client_version, server_name, server_version, protocol_version, era, pid, "
    "client_pid, started_at, last_seen_at, ended_at, hidden"
)

_EXCHANGE_COLUMNS = (
    "e.id, e.session_id, e.initiator, e.method, e.target, e.rpc_id, e.request_msg_id, "
    "e.response_msg_id, e.started_at, e.ended_at, e.duration_ms, e.status, e.error_code, "
    "e.error_message, e.request_tokens, e.response_tokens, e.parent_id, e.chain_root_id"
)


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return psutil.pid_exists(pid)
    except Exception:  # pragma: no cover - platform specific
        return False


def _loads(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


class Query:
    """Read-only access to captured traffic."""

    def __init__(self, db: Path | str | None = None, now=time.time):
        self._conn = connect(db)
        self._lock = threading.Lock()
        self._now = now

    def close(self) -> None:
        self._conn.close()

    def _all(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    # -- liveness ---------------------------------------------------------

    def _is_live(self, session: dict[str, Any]) -> bool:
        if session.get("ended_at"):
            return False
        if session.get("pid") is not None:
            return _pid_alive(session["pid"])
        return self._now() - session["last_seen_at"] < IDLE_AFTER_S

    def effective_status(self, exchange: dict[str, Any], live: bool) -> str:
        """Stored status, with stale pending calls surfaced as hung/abandoned."""
        if exchange["status"] != "pending":
            return exchange["status"]
        if not live:
            return "abandoned"
        if self._now() - exchange["started_at"] > HUNG_AFTER_S:
            return "hung"
        return "pending"

    def _decorate_session(self, session: dict[str, Any]) -> dict[str, Any]:
        session["live"] = self._is_live(session)
        session["hidden"] = bool(session["hidden"])
        session["display_name"] = (
            session.get("name") or session.get("server_name") or session.get("target")
            or session["id"])
        return session

    def _decorate_exchange(self, exchange: dict[str, Any], live: bool) -> dict[str, Any]:
        exchange["status"] = self.effective_status(exchange, live)
        if exchange["status"] in ("hung", "pending"):
            exchange["duration_ms"] = round((self._now() - exchange["started_at"]) * 1000, 3)
        return exchange

    # -- sessions & runs --------------------------------------------------

    def list_sessions(
        self,
        *,
        run_key: str | None = None,
        server: str | None = None,
        limit: int = 100,
        include_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        where, params = ["1=1"], []
        if run_key:
            where.append("s.run_key = ?")
            params.append(run_key)
        if server:
            where.append("(s.server_name = ? OR s.name = ?)")
            params += [server, server]
        if not include_hidden:
            where.append("s.hidden = 0")
        sessions = self._all(
            f"""SELECT {", ".join("s." + c.strip() for c in _SESSION_COLUMNS.split(","))},
                    COUNT(e.id) AS exchange_count,
                    SUM(CASE WHEN e.status IN ('error', 'tool_error') THEN 1 ELSE 0 END)
                        AS error_count,
                    SUM(CASE WHEN e.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
                    COALESCE(SUM(e.request_tokens + e.response_tokens), 0) AS tokens
                FROM sessions s LEFT JOIN exchanges e ON e.session_id = s.id
                WHERE {" AND ".join(where)}
                GROUP BY s.id ORDER BY s.last_seen_at DESC LIMIT ?""",
            [*params, limit],
        )
        for session in sessions:
            self._decorate_session(session)
            session["error_count"] = session["error_count"] or 0
            session["pending_count"] = session["pending_count"] or 0
        return sessions

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._one(f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE id = ?",
                            (session_id,))
        if not session:
            return None
        self._decorate_session(session)
        session["exchanges"] = self.exchanges(session_id=session_id, live=session["live"])
        counts = self._one(
            """SELECT COUNT(*) AS messages,
                   SUM(CASE WHEN kind = 'notification' THEN 1 ELSE 0 END) AS notifications,
                   SUM(CASE WHEN kind = 'invalid' THEN 1 ELSE 0 END) AS invalid
               FROM messages WHERE session_id = ?""",
            (session_id,),
        ) or {}
        session["message_count"] = counts.get("messages") or 0
        session["notification_count"] = counts.get("notifications") or 0
        session["invalid_count"] = counts.get("invalid") or 0
        return session

    def list_runs(self, limit: int = 50, include_hidden: bool = False) -> list[dict[str, Any]]:
        """Group sessions by the client process (or client identity) that drove them."""
        hidden = "" if include_hidden else "AND s.hidden = 0"
        runs = self._all(
            f"""SELECT COALESCE(s.run_key, 'session:' || s.id) AS run_key,
                    MAX(s.client_app) AS client_app, MAX(s.client_name) AS client_name,
                    MIN(s.started_at) AS started_at, MAX(s.last_seen_at) AS last_seen_at,
                    COUNT(DISTINCT s.id) AS session_count,
                    GROUP_CONCAT(DISTINCT COALESCE(s.name, s.server_name, s.target))
                        AS servers
                FROM sessions s WHERE 1=1 {hidden}
                GROUP BY COALESCE(s.run_key, 'session:' || s.id)
                ORDER BY last_seen_at DESC LIMIT ?""",
            (limit,),
        )
        for run in runs:
            run["servers"] = sorted(filter(None, (run["servers"] or "").split(",")))
            stats = self._one(
                f"""SELECT COUNT(e.id) AS exchanges,
                        SUM(CASE WHEN e.status IN ('error', 'tool_error') THEN 1 ELSE 0 END)
                            AS errors,
                        COALESCE(SUM(e.request_tokens + e.response_tokens), 0) AS tokens
                    FROM exchanges e JOIN sessions s ON s.id = e.session_id
                    WHERE {self._run_clause()} {hidden}""",
                self._run_params(run["run_key"]),
            ) or {}
            run["exchange_count"] = stats.get("exchanges") or 0
            run["error_count"] = stats.get("errors") or 0
            run["tokens"] = stats.get("tokens") or 0
            sessions = self._all(
                f"SELECT {_SESSION_COLUMNS} FROM sessions s WHERE {self._run_clause()}",
                self._run_params(run["run_key"]))
            run["live"] = any(self._is_live(s) for s in sessions)
        return runs

    @staticmethod
    def _run_clause() -> str:
        return "(s.run_key = ? OR (s.run_key IS NULL AND 'session:' || s.id = ?))"

    @staticmethod
    def _run_params(run_key: str) -> tuple[str, str]:
        return (run_key, run_key)

    def get_run(self, run_key: str, include_hidden: bool = False) -> dict[str, Any] | None:
        hidden = "" if include_hidden else "AND s.hidden = 0"
        sessions = self._all(
            f"""SELECT {_SESSION_COLUMNS} FROM sessions s
                WHERE {self._run_clause()} {hidden} ORDER BY started_at""",
            self._run_params(run_key),
        )
        if not sessions:
            return None
        live_by_session = {}
        for session in sessions:
            self._decorate_session(session)
            live_by_session[session["id"]] = session["live"]
        timeline = self._all(
            f"""SELECT {_EXCHANGE_COLUMNS} FROM exchanges e
                WHERE e.session_id IN ({",".join("?" * len(sessions))})
                ORDER BY e.started_at, e.id""",
            [s["id"] for s in sessions],
        )
        for exchange in timeline:
            self._decorate_exchange(exchange, live_by_session[exchange["session_id"]])
        return {
            "run_key": run_key,
            "client_app": next((s["client_app"] for s in sessions if s["client_app"]), None),
            "client_name": next((s["client_name"] for s in sessions if s["client_name"]), None),
            "started_at": sessions[0]["started_at"],
            "last_seen_at": max(s["last_seen_at"] for s in sessions),
            "live": any(live_by_session.values()),
            "sessions": sessions,
            "timeline": timeline,
        }

    # -- exchanges & messages --------------------------------------------

    def exchanges(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        method: str | None = None,
        target: str | None = None,
        text: str | None = None,
        limit: int = 1000,
        live: bool | None = None,
        include_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        where, params = ["1=1"], []
        if session_id:
            where.append("e.session_id = ?")
            params.append(session_id)
        if method:
            where.append("e.method = ?")
            params.append(method)
        if target:
            where.append("e.target = ?")
            params.append(target)
        if status in ("ok", "error", "tool_error", "input_required", "cancelled"):
            where.append("e.status = ?")
            params.append(status)
        elif status in ("pending", "hung", "abandoned"):
            where.append("e.status = 'pending'")
        if text:
            where.append(
                """EXISTS (SELECT 1 FROM messages m WHERE m.exchange_id = e.id
                           AND m.body LIKE ? ESCAPE '\\')""")
            escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        if not include_hidden:
            where.append("s.hidden = 0")
        rows = self._all(
            f"""SELECT {_EXCHANGE_COLUMNS}, s.ended_at AS s_ended_at, s.pid AS s_pid,
                    s.last_seen_at AS s_last_seen_at,
                    COALESCE(s.name, s.server_name, s.target) AS server
                FROM exchanges e JOIN sessions s ON s.id = e.session_id
                WHERE {" AND ".join(where)}
                ORDER BY e.started_at DESC, e.id DESC LIMIT ?""",
            [*params, limit],
        )
        live_cache: dict[str, bool] = {}
        result = []
        for row in rows:
            session_live = live
            if session_live is None:
                if row["session_id"] not in live_cache:
                    live_cache[row["session_id"]] = self._is_live({
                        "ended_at": row["s_ended_at"], "pid": row["s_pid"],
                        "last_seen_at": row["s_last_seen_at"]})
                session_live = live_cache[row["session_id"]]
            for key in ("s_ended_at", "s_pid", "s_last_seen_at"):
                row.pop(key)
            self._decorate_exchange(row, session_live)
            if status in ("pending", "hung", "abandoned") and row["status"] != status:
                continue
            result.append(row)
        result.reverse()
        return result

    def get_exchange(self, exchange_id: int) -> dict[str, Any] | None:
        exchange = self._one(
            f"""SELECT {_EXCHANGE_COLUMNS} FROM exchanges e WHERE e.id = ?""",
            (exchange_id,))
        if not exchange:
            return None
        session = self.get_session_header(exchange["session_id"])
        self._decorate_exchange(exchange, bool(session and session["live"]))
        exchange["session"] = session
        exchange["request"] = self.get_message(exchange["request_msg_id"])
        exchange["response"] = (
            self.get_message(exchange["response_msg_id"])
            if exchange["response_msg_id"] else None)
        exchange["chain"] = self._chain(exchange)
        return exchange

    def get_session_header(self, session_id: str) -> dict[str, Any] | None:
        session = self._one(f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE id = ?",
                            (session_id,))
        return self._decorate_session(session) if session else None

    def _chain(self, exchange: dict[str, Any]) -> list[dict[str, Any]]:
        """All exchanges of a multi round-trip chain, in order."""
        root = exchange["chain_root_id"] or exchange["id"]
        rows = self._all(
            f"""SELECT {_EXCHANGE_COLUMNS} FROM exchanges e
                WHERE e.id = ? OR e.chain_root_id = ? ORDER BY e.id""",
            (root, root))
        return rows if len(rows) > 1 else []

    def get_message(self, message_id: int) -> dict[str, Any] | None:
        message = self._one("SELECT * FROM messages WHERE id = ?", (message_id,))
        if not message:
            return None
        message["body"] = _loads(message["body"])
        message["headers"] = _loads(message["headers"])
        return message

    def messages(
        self,
        *,
        session_id: str | None = None,
        after_id: int = 0,
        limit: int = 500,
        include_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        where, params = ["m.id > ?"], [after_id]
        if session_id:
            where.append("m.session_id = ?")
            params.append(session_id)
        if not include_hidden:
            where.append("s.hidden = 0")
        rows = self._all(
            f"""SELECT m.id, m.session_id, m.exchange_id, m.ts, m.direction, m.kind,
                    m.method, m.rpc_id, m.size, m.tokens, m.note,
                    COALESCE(s.name, s.server_name, s.target) AS server
                FROM messages m JOIN sessions s ON s.id = m.session_id
                WHERE {" AND ".join(where)} ORDER BY m.id LIMIT ?""",
            [*params, limit],
        )
        return rows

    def latest_message_id(self) -> int:
        row = self._one("SELECT COALESCE(MAX(id), 0) AS id FROM messages")
        return int(row["id"]) if row else 0

    def messages_for(self, session_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        """Full message rows (with parsed bodies) of one session."""
        sql = "SELECT * FROM messages WHERE session_id = ?"
        params: list[Any] = [session_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        rows = self._all(sql + " ORDER BY id", params)
        for row in rows:
            row["body"] = _loads(row["body"])
            row["headers"] = _loads(row["headers"])
        return rows

    def responses_for(self, method: str, session_ids: list[str]) -> list[dict[str, Any]]:
        """Response messages (parsed) of all exchanges of ``method`` in some sessions."""
        if not session_ids:
            return []
        rows = self._all(
            f"""SELECT e.id AS exchange_id, e.session_id, e.started_at, m.body
                FROM exchanges e JOIN messages m ON m.id = e.response_msg_id
                WHERE e.method = ? AND e.status = 'ok'
                  AND e.session_id IN ({",".join("?" * len(session_ids))})
                ORDER BY e.started_at""",
            [method, *session_ids],
        )
        for row in rows:
            row["body"] = _loads(row["body"])
        return rows

    def stats(self) -> dict[str, Any]:
        row = self._one(
            """SELECT
                 (SELECT COUNT(*) FROM sessions WHERE hidden = 0) AS sessions,
                 (SELECT COUNT(*) FROM exchanges e JOIN sessions s ON s.id = e.session_id
                    WHERE s.hidden = 0) AS exchanges,
                 (SELECT COUNT(*) FROM messages m JOIN sessions s ON s.id = m.session_id
                    WHERE s.hidden = 0) AS messages,
                 (SELECT COUNT(*) FROM exchanges e JOIN sessions s ON s.id = e.session_id
                    WHERE s.hidden = 0 AND e.status IN ('error', 'tool_error')) AS errors""")
        return row or {}

    def clear(self) -> None:
        with self._lock:
            self._conn.executescript(
                "DELETE FROM messages; DELETE FROM exchanges; DELETE FROM sessions;")
            self._conn.commit()


def resolve_scope(
    q: Query,
    *,
    session_id: str | None = None,
    run_key: str | None = None,
    server: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Sessions an analysis should look at, newest first."""
    if session_id:
        session = q.get_session_header(session_id)
        return [session] if session else []
    return q.list_sessions(run_key=run_key, server=server, limit=limit)
