"""Turns raw captured frames into sessions, exchanges and messages.

Every capture mode (stdio wrapper, HTTP proxy, passive sniffer) feeds frames
through a :class:`Recorder`. It owns request/response pairing, multi
round-trip chains and identity extraction, so the capture code only has to
know which direction bytes flowed in.
"""

import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcphawk.protocol import jsonrpc
from mcphawk.protocol import mcp as proto
from mcphawk.protocol.masking import mask_headers, mask_text, mask_value
from mcphawk.protocol.tokens import estimate_content, estimate_json, estimate_text
from mcphawk.store.db import connect

C2S = "c2s"
S2C = "s2c"

STATUS_PENDING = "pending"
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_TOOL_ERROR = "tool_error"
STATUS_INPUT_REQUIRED = "input_required"
STATUS_CANCELLED = "cancelled"

HIDDEN_SERVER_NAMES = frozenset({"mcphawk"})
MAX_EARLY = 64


@dataclass
class _SessionState:
    pending: dict[tuple[str, str], tuple[int, str, float]] = field(default_factory=dict)
    # requestState token -> exchange that asked for more input
    input_states: dict[str, int] = field(default_factory=dict)
    # responses that were recorded before their request: the two directions
    # are captured by different threads, and a fast server can win the race
    early: dict[tuple[str, str], tuple[int, dict[str, Any], str, float]] = field(
        default_factory=dict)
    identity: dict[str, Any] = field(default_factory=dict)


class Recorder:
    """Thread-safe writer for one capturing process."""

    def __init__(
        self,
        db: Path | str | None = None,
        mask: bool = True,
        on_record: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._conn = connect(db)
        self._lock = threading.Lock()
        self._mask = mask
        self._on_record = on_record
        self._sessions: dict[str, _SessionState] = {}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- sessions ---------------------------------------------------------

    def open_session(
        self,
        *,
        capture: str,
        transport: str,
        name: str | None = None,
        target: str | None = None,
        pid: int | None = None,
        client_pid: int | None = None,
        client_app: str | None = None,
        client_key: str | None = None,
        ts: float | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex[:12]
        now = ts or time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO sessions (id, client_key, name, capture, transport, target,
                       client_app, pid, client_pid, started_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, client_key, name, capture, transport,
                 mask_text(target) if (target and self._mask) else target,
                 client_app, pid, client_pid, now, now),
            )
            self._conn.commit()
            self._sessions[session_id] = _SessionState()
        return session_id

    def end_session(self, session_id: str, ts: float | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (ts or time.time(), session_id),
            )
            self._conn.commit()

    # -- messages ---------------------------------------------------------

    def record(
        self,
        session_id: str,
        direction: str,
        raw: str | bytes,
        *,
        headers: dict[str, str] | None = None,
        ts: float | None = None,
    ) -> list[int]:
        """Record one wire frame (a message or a batch). Returns message ids."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        raw = raw.strip()
        if not raw:
            return []
        now = ts or time.time()
        header_json = None
        if headers:
            header_json = json.dumps(mask_headers(headers) if self._mask else headers)

        with self._lock:
            state = self._sessions.setdefault(session_id, _SessionState())
            messages = jsonrpc.parse_frame(raw)
            ids: list[int] = []
            if messages is None:
                ids.append(self._insert_invalid(session_id, direction, raw, header_json, now))
            else:
                batch_note = f"batch of {len(messages)}" if len(messages) > 1 else None
                for msg in messages:
                    ids.append(self._record_one(
                        session_id, state, direction, msg, header_json, now, batch_note))
            self._conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now, session_id))
            self._conn.commit()

        if self._on_record:
            for message_id in ids:
                self._on_record({"session_id": session_id, "message_id": message_id})
        return ids

    def _insert_invalid(self, session_id, direction, raw, header_json, now) -> int:
        body = mask_text(raw) if self._mask else raw
        cur = self._conn.execute(
            """INSERT INTO messages (session_id, ts, direction, kind, size, tokens, body,
                   headers, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, now, direction, jsonrpc.INVALID, len(raw.encode()),
             estimate_text(raw), body, header_json, "not JSON"),
        )
        return int(cur.lastrowid)

    def _record_one(self, session_id, state, direction, msg, header_json, now, note) -> int:
        kind = jsonrpc.classify(msg)
        method = msg.get("method") if isinstance(msg.get("method"), str) else None
        rpc_key = jsonrpc.id_key(msg.get("id"))
        stored = mask_value(msg) if self._mask else msg
        body = json.dumps(stored, ensure_ascii=False)
        size = len(json.dumps(msg, ensure_ascii=False).encode())

        cur = self._conn.execute(
            """INSERT INTO messages (session_id, ts, direction, kind, method, rpc_id, size,
                   tokens, body, headers, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, now, direction, kind, method, rpc_key, size,
             estimate_text(body), body, header_json, note),
        )
        message_id = int(cur.lastrowid)

        if kind == jsonrpc.REQUEST:
            exchange_id = self._open_exchange(
                session_id, state, direction, msg, method, rpc_key, message_id, now)
            self._link(message_id, exchange_id)
            self._absorb_request_identity(session_id, state, msg)
            initiator = "client" if direction == C2S else "server"
            early = state.early.pop((initiator, rpc_key), None) if rpc_key else None
            if early:
                response_id, response, response_kind, response_ts = early
                state.pending.pop((initiator, rpc_key), None)
                self._close_exchange(session_id, state, exchange_id, method, response,
                                     response_kind, response_id, now, max(now, response_ts))
                self._link(response_id, exchange_id)
                self._conn.execute("UPDATE messages SET note = NULL WHERE id = ?",
                                   (response_id,))
        elif kind in (jsonrpc.RESPONSE, jsonrpc.ERROR):
            initiator = "client" if direction == S2C else "server"
            pending = state.pending.pop((initiator, rpc_key), None) if rpc_key else None
            if pending:
                exchange_id, request_method, started = pending
                self._close_exchange(
                    session_id, state, exchange_id, request_method, msg, kind,
                    message_id, started, now)
                self._link(message_id, exchange_id)
            else:
                if rpc_key:
                    state.early[(initiator, rpc_key)] = (message_id, msg, kind, now)
                    if len(state.early) > MAX_EARLY:
                        state.early.pop(next(iter(state.early)))
                self._conn.execute(
                    "UPDATE messages SET note = ? WHERE id = ?",
                    ("no matching request", message_id))
        elif kind == jsonrpc.NOTIFICATION and method == "notifications/cancelled":
            self._cancel(state, direction, msg, now)
        return message_id

    def _link(self, message_id: int, exchange_id: int) -> None:
        self._conn.execute(
            "UPDATE messages SET exchange_id = ? WHERE id = ?", (exchange_id, message_id))

    def _open_exchange(self, session_id, state, direction, msg, method, rpc_key,
                       message_id, now) -> int:
        initiator = "client" if direction == C2S else "server"
        parent_id = root_id = None
        token = proto.request_state(msg)
        if token and token in state.input_states:
            parent_id = state.input_states.pop(token)
            row = self._conn.execute(
                "SELECT chain_root_id FROM exchanges WHERE id = ?", (parent_id,)).fetchone()
            root_id = (row["chain_root_id"] if row else None) or parent_id
        cur = self._conn.execute(
            """INSERT INTO exchanges (session_id, initiator, method, target, rpc_id,
                   request_msg_id, started_at, request_tokens, parent_id, chain_root_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, initiator, method, proto.target_of(msg), rpc_key, message_id,
             now, estimate_json(msg.get("params")), parent_id, root_id),
        )
        exchange_id = int(cur.lastrowid)
        if rpc_key:
            state.pending[(initiator, rpc_key)] = (exchange_id, method, now)
        return exchange_id

    def _close_exchange(self, session_id, state, exchange_id, request_method, msg, kind,
                        message_id, started, now) -> None:
        code = error_message = None
        if kind == jsonrpc.ERROR:
            status = STATUS_ERROR
            code, error_message = proto.error_of(msg)
        elif proto.result_type(msg) == proto.RESULT_INPUT_REQUIRED:
            status = STATUS_INPUT_REQUIRED
            token = proto.request_state(msg)
            if token:
                state.input_states[token] = exchange_id
        elif request_method == "tools/call" and proto.is_tool_error(msg):
            status = STATUS_TOOL_ERROR
            error_message = proto.tool_error_text(msg)
        else:
            status = STATUS_OK

        result = msg.get("result") if isinstance(msg.get("result"), dict) else None
        if request_method == "tools/call" and result is not None and "content" in result:
            tokens = estimate_content(result.get("content"))
        else:
            tokens = estimate_json(result if result is not None else msg.get("error"))

        self._conn.execute(
            """UPDATE exchanges SET response_msg_id = ?, ended_at = ?, duration_ms = ?,
                   status = ?, error_code = ?, error_message = ?, response_tokens = ?
               WHERE id = ?""",
            (message_id, now, round((now - started) * 1000, 3), status, code,
             error_message, tokens, exchange_id),
        )
        if kind == jsonrpc.RESPONSE:
            self._absorb_response_identity(session_id, state, msg, request_method)

    def _cancel(self, state, direction, msg, now) -> None:
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        rpc_key = jsonrpc.id_key(params.get("requestId"))
        initiator = "client" if direction == C2S else "server"
        pending = state.pending.pop((initiator, rpc_key), None) if rpc_key else None
        if pending:
            exchange_id, _, started = pending
            reason = params.get("reason")
            self._conn.execute(
                """UPDATE exchanges SET status = ?, ended_at = ?, duration_ms = ?,
                       error_message = ? WHERE id = ?""",
                (STATUS_CANCELLED, now, round((now - started) * 1000, 3),
                 str(reason) if reason else None, exchange_id),
            )

    # -- identity ---------------------------------------------------------

    def _absorb_request_identity(self, session_id, state, msg) -> None:
        updates: dict[str, Any] = {}
        client = proto.client_info(msg)
        if client:
            updates["client_name"] = client["name"]
            updates["client_version"] = client["version"]
        version = proto.protocol_version(msg)
        if version:
            updates["protocol_version"] = version
            updates["era"] = proto.era_of_version(version)
        self._update_identity(session_id, state, updates)

    def _absorb_response_identity(self, session_id, state, msg, request_method) -> None:
        updates: dict[str, Any] = {}
        server = proto.server_info(msg, request_method)
        if server:
            updates["server_name"] = server["name"]
            updates["server_version"] = server["version"]
            if server["name"].lower() in HIDDEN_SERVER_NAMES:
                updates["hidden"] = 1
        if request_method == "initialize":
            version = proto.negotiated_version(msg)
            if version:
                updates["protocol_version"] = version
                updates["era"] = proto.era_of_version(version)
        self._update_identity(session_id, state, updates)

    def _update_identity(self, session_id, state, updates: dict[str, Any]) -> None:
        changed = {k: v for k, v in updates.items() if state.identity.get(k) != v}
        if not changed:
            return
        state.identity.update(changed)
        assignments = ", ".join(f"{column} = ?" for column in changed)
        self._conn.execute(
            f"UPDATE sessions SET {assignments} WHERE id = ?",  # column names are fixed
            (*changed.values(), session_id),
        )
