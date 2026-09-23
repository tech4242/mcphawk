"""Passive capture: reconstruct MCP traffic from packets, no config changes.

Only plaintext traffic can be read, which in practice means local HTTP
servers; use the proxy for HTTPS or remote servers. Needs packet-capture
privileges (usually ``sudo``).
"""

import logging
import platform
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from mcphawk.capture.http1 import Http1Stream, looks_like_request, looks_like_response
from mcphawk.capture.http_sessions import SESSION_HEADER, HttpSessions, header
from mcphawk.capture.sse import SSEParser
from mcphawk.capture.stdio import LineFramer
from mcphawk.protocol import jsonrpc
from mcphawk.store import C2S, S2C, Recorder

logger = logging.getLogger(__name__)

FIN, SYN, RST = 0x01, 0x02, 0x04
MAX_OUT_OF_ORDER = 256
SEQ_MOD = 2**32

Endpoint = tuple[str, int]


def _mcp_messages(body: bytes) -> list[dict[str, Any]] | None:
    """JSON-RPC messages in a body, or None if it is not MCP traffic."""
    messages = jsonrpc.parse_frame(body.decode("utf-8", "replace"))
    if messages and all("jsonrpc" in m for m in messages):
        return messages
    return None


@dataclass
class _Direction:
    next_seq: int | None = None
    out_of_order: dict[int, bytes] = field(default_factory=dict)

    def accept(self, seq: int, payload: bytes, syn: bool) -> list[bytes]:
        """In-order payload segments released by this packet."""
        if syn:
            self.next_seq = (seq + 1) % SEQ_MOD
            seq = self.next_seq
        if not payload:
            return []
        if self.next_seq is None:
            self.next_seq = seq
        offset = (seq - self.next_seq) % SEQ_MOD
        if offset >= SEQ_MOD // 2:  # retransmission overlapping acknowledged data
            overlap = SEQ_MOD - offset
            if overlap >= len(payload):
                return []
            payload, seq = payload[overlap:], self.next_seq
        elif offset:
            if len(self.out_of_order) < MAX_OUT_OF_ORDER:
                self.out_of_order[seq] = payload
            return []
        released = [payload]
        self.next_seq = (seq + len(payload)) % SEQ_MOD
        while self.next_seq in self.out_of_order:
            segment = self.out_of_order.pop(self.next_seq)
            released.append(segment)
            self.next_seq = (self.next_seq + len(segment)) % SEQ_MOD
        return released


@dataclass
class _Request:
    method: str
    path: str
    headers: dict[str, str]
    session_id: str | None


class _Connection:
    """One TCP connection; figures out its protocol from the first bytes."""

    def __init__(self, sniffer: "Sniffer", a: Endpoint, b: Endpoint):
        self.sniffer = sniffer
        self.directions = {a: _Direction(), b: _Direction()}
        self.client: Endpoint | None = None
        self.server: Endpoint | None = None
        self.mode: str | None = None  # "http" | "json" | "other"
        self.streams: dict[Endpoint, Any] = {}
        self.pending: deque[_Request] = deque()
        self.json_session: str | None = None

    def packet(self, src: Endpoint, seq: int, flags: int, payload: bytes) -> None:
        for segment in self.directions[src].accept(seq, payload, bool(flags & SYN)):
            self._data(src, segment)

    def _data(self, src: Endpoint, data: bytes) -> None:
        if self.mode is None:
            self._detect(src, data)
        if self.mode in ("http", "json"):
            self.streams[src].feed(data)

    def _detect(self, src: Endpoint, data: bytes) -> None:
        other = next(e for e in self.directions if e != src)
        stripped = data.lstrip()
        if looks_like_request(data):
            self.client, self.server = src, other
        elif looks_like_response(data):
            self.client, self.server = other, src
        elif stripped.startswith((b"{", b"[")):
            self.mode = "json"
            self.client, self.server = src, other
            self.streams = {
                src: LineFramer(lambda line: self._json_line(C2S, line)),
                other: LineFramer(lambda line: self._json_line(S2C, line)),
            }
            return
        else:
            self.mode = "other"
            return
        self.mode = "http"
        self.streams = {
            self.client: _RequestStream(self),
            self.server: _ResponseStream(self),
        }

    def _json_line(self, direction: str, line: bytes) -> None:
        if _mcp_messages(line) is None:
            return
        if self.json_session is None:
            host, port = self.server
            self.json_session = self.sniffer.recorder.open_session(
                capture="sniff", transport="unknown", target=f"tcp://{host}:{port}")
        self.sniffer.recorder.record(self.json_session, direction, line)

    def upstream(self, path: str) -> str:
        host, port = self.server
        host = f"[{host}]" if ":" in host else host
        return f"http://{host}:{port}{urlsplit(path).path}"

    def close(self) -> None:
        for stream in self.streams.values():
            if isinstance(stream, _ResponseStream):
                stream.parser.close()
            elif isinstance(stream, LineFramer):
                stream.flush()


class _RequestStream:
    def __init__(self, conn: _Connection):
        self.conn = conn
        self.head: tuple[str, dict[str, str]] | None = None
        self.body = bytearray()
        self.parser = Http1Stream(False, self._head, self.body.extend, self._end)

    def feed(self, data: bytes) -> None:
        self.parser.feed(data)

    def _head(self, start: str, headers: dict[str, str]) -> None:
        self.head = (start, headers)
        self.body.clear()

    def _end(self) -> None:
        start, headers = self.head or ("", {})
        parts = start.split(" ")
        method, path = (parts[0], parts[1]) if len(parts) > 1 else ("", "/")
        session_id = None
        messages = _mcp_messages(bytes(self.body)) if self.body else None
        if messages is not None:
            sessions = self.conn.sniffer.sessions
            session_id = sessions.for_request(
                self.conn.upstream(path), headers, messages, query=urlsplit(path).query)
            self.conn.sniffer.recorder.record(session_id, C2S, bytes(self.body),
                                              headers=headers)
        self.conn.pending.append(_Request(method, path, headers, session_id))


class _ResponseStream:
    def __init__(self, conn: _Connection):
        self.conn = conn
        self.request: _Request | None = None
        self.sse: SSEParser | None = None
        self.session_id: str | None = None
        self.body = bytearray()
        self.parser = Http1Stream(True, self._head, self._data, self._end)

    def feed(self, data: bytes) -> None:
        self.parser.feed(data)

    def _head(self, start: str, headers: dict[str, str]) -> None:
        self.request = self.conn.pending.popleft() if self.conn.pending else None
        self.body.clear()
        self.sse = None
        self.session_id = self.request.session_id if self.request else None
        if self.request is None:
            return
        upstream = self.conn.upstream(self.request.path)
        sessions = self.conn.sniffer.sessions
        if self.session_id:
            sessions.bind_session_header(self.session_id, upstream,
                                         header(headers, SESSION_HEADER))
        if "text/event-stream" in (header(headers, "content-type") or ""):
            self.sse = SSEParser()
            if self.session_id is None:
                self.session_id = sessions.for_sse_stream(upstream, self.request.headers)

    def _data(self, data: bytes) -> None:
        if self.sse is None:
            self.body.extend(data)
            return
        for event in self.sse.feed(data):
            if event.event == "endpoint" and self.session_id is None and self.request:
                self.session_id = self.conn.sniffer.sessions.open_legacy_sse(
                    self.conn.upstream(self.request.path), event.data)
            elif self.session_id and _mcp_messages(event.data.encode()) is not None:
                self.conn.sniffer.recorder.record(self.session_id, S2C, event.data)

    def _end(self) -> None:
        if (self.sse is None and self.session_id and self.body
                and _mcp_messages(bytes(self.body)) is not None):
            self.conn.sniffer.recorder.record(self.session_id, S2C, bytes(self.body))
        self.body.clear()


class Sniffer:
    def __init__(self, recorder: Recorder, excluded_ports: set[int] | None = None):
        self.recorder = recorder
        self.sessions = HttpSessions(recorder, capture="sniff")
        self.excluded_ports = excluded_ports or set()
        self._connections: dict[frozenset[Endpoint], _Connection] = {}

    def process(self, src: Endpoint, dst: Endpoint, seq: int, flags: int,
                payload: bytes) -> None:
        if src[1] in self.excluded_ports or dst[1] in self.excluded_ports:
            return
        key = frozenset((src, dst))
        conn = self._connections.get(key)
        if conn is None:
            if not payload and not flags & SYN:
                return
            conn = self._connections[key] = _Connection(self, src, dst)
        try:
            conn.packet(src, seq, flags, payload)
        except Exception:
            logger.exception("dropping connection %s <-> %s after parse error", src, dst)
            self._connections.pop(key, None)
            return
        if flags & (FIN | RST):
            conn.close()
            self._connections.pop(key, None)

    def handle_packet(self, pkt: Any) -> None:
        """Scapy callback."""
        from scapy.all import IP, TCP, IPv6

        if not pkt.haslayer(TCP):
            return
        ip = pkt[IP] if pkt.haslayer(IP) else pkt[IPv6] if pkt.haslayer(IPv6) else None
        if ip is None:
            return
        tcp = pkt[TCP]
        self.process((ip.src, int(tcp.sport)), (ip.dst, int(tcp.dport)), int(tcp.seq),
                     int(tcp.flags), bytes(tcp.payload))


def default_interface() -> str | None:
    return "lo0" if platform.system() == "Darwin" else None


def run_sniffer(filter_expr: str, recorder: Recorder, interface: str | None = None,
                excluded_ports: set[int] | None = None) -> None:  # pragma: no cover
    """Blocking capture loop (needs packet-capture privileges)."""
    logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
    from scapy.all import conf, sniff

    conf.use_pcap = True
    sniffer = Sniffer(recorder, excluded_ports)
    sniff(filter=filter_expr, iface=interface or default_interface(),
          prn=sniffer.handle_packet, store=False)
