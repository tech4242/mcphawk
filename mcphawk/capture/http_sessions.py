"""Grouping HTTP exchanges into sessions.

Over stdio a session is simply the lifetime of the process. Over HTTP it has
to be inferred, and each protocol generation needs a different key:

* 2025-era Streamable HTTP: the ``Mcp-Session-Id`` header;
* legacy HTTP+SSE: the query string of the POST endpoint announced on the
  SSE stream (e.g. ``/messages?session_id=abc``);
* 2026-07-28 (stateless): nothing protocol-level, so the client identity from
  ``_meta``, with a fresh session after a period of inactivity.
"""

import threading
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcphawk.protocol import mcp as proto
from mcphawk.store import Recorder

SESSION_HEADER = "mcp-session-id"
IDLE_ROLLOVER_S = 30 * 60


def _endpoint_key(upstream: str, query: str) -> tuple[str, str]:
    """Legacy SSE streams and their POSTs use different paths on one origin."""
    parts = urlsplit(upstream)
    return (urlunsplit((parts.scheme, parts.netloc, "", "", "")), "ep:" + query)


def header(headers: dict[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    name = name.lower()
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


class HttpSessions:
    def __init__(self, recorder: Recorder, capture: str, now=time.time):
        self.recorder = recorder
        self.capture = capture
        self._now = now
        self._lock = threading.Lock()
        self._keys: dict[tuple[str, str], str] = {}
        self._last_seen: dict[str, float] = {}

    def _open(self, upstream: str, name: str | None, transport: str) -> str:
        # HTTP sessions have no client process; runs group them by client identity
        return self.recorder.open_session(
            capture=self.capture, transport=transport, name=name, target=upstream)

    def _touch(self, session_id: str) -> str:
        self._last_seen[session_id] = self._now()
        return session_id

    def for_request(
        self,
        upstream: str,
        headers: dict[str, str] | None,
        messages: list[dict[str, Any]],
        *,
        name: str | None = None,
        query: str = "",
    ) -> str:
        """Session a client->server POST belongs to (created if needed)."""
        with self._lock:
            session_header = header(headers, SESSION_HEADER)
            if session_header:
                key = (upstream, "sid:" + session_header)
                if key not in self._keys:
                    self._keys[key] = self._open(upstream, name, "streamable_http")
                return self._touch(self._keys[key])

            if query:
                existing = self._keys.get(_endpoint_key(upstream, query))
                if existing:
                    return self._touch(existing)

            if any(m.get("method") == "initialize" for m in messages):
                # legacy handshake: the session id arrives on the response
                return self._touch(self._open(upstream, name, "streamable_http"))

            client = next((c for c in map(proto.client_info, messages) if c), None)
            label = client["name"] if client else "anonymous"
            key = (upstream, "client:" + label)
            current = self._keys.get(key)
            if current and self._now() - self._last_seen.get(current, 0) < IDLE_ROLLOVER_S:
                return self._touch(current)
            self._keys[key] = self._open(upstream, name, "streamable_http")
            return self._touch(self._keys[key])

    def bind_session_header(self, session_id: str, upstream: str, value: str | None) -> None:
        """Remember the ``Mcp-Session-Id`` a server assigned to a session."""
        if value:
            with self._lock:
                self._keys.setdefault((upstream, "sid:" + value), session_id)

    def for_sse_stream(self, upstream: str, headers: dict[str, str] | None,
                       name: str | None = None) -> str | None:
        """Session of a GET event stream, if it belongs to a known session."""
        session_header = header(headers, SESSION_HEADER)
        if not session_header:
            return None
        with self._lock:
            session_id = self._keys.get((upstream, "sid:" + session_header))
            return self._touch(session_id) if session_id else None

    def open_legacy_sse(self, upstream: str, endpoint: str, name: str | None = None) -> str:
        """A legacy HTTP+SSE stream announced its POST endpoint."""
        query = urlsplit(endpoint).query
        with self._lock:
            session_id = self._open(upstream, name, "http_sse")
            self._keys[_endpoint_key(upstream, query)] = session_id
            return self._touch(session_id)
