"""Incremental Server-Sent Events parser (WHATWG event-stream format)."""

from dataclasses import dataclass


@dataclass
class SSEEvent:
    event: str
    data: str
    id: str | None = None


class SSEParser:
    """Feed arbitrary byte chunks; get complete events back.

    Handles LF, CRLF and CR line endings, multi-line ``data:`` fields,
    comments and events split across chunk boundaries.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._pending = b""
        self._event = ""
        self._data: list[str] = []
        self._id: str | None = None

    def feed(self, chunk: bytes | str) -> list[SSEEvent]:
        if isinstance(chunk, bytes):
            chunk = self._pending + chunk
            try:
                text = chunk.decode("utf-8")
                self._pending = b""
            except UnicodeDecodeError as exc:
                # keep a trailing partial multi-byte sequence for the next chunk
                text = chunk[:exc.start].decode("utf-8")
                self._pending = chunk[exc.start:]
        else:
            text = chunk
        self._buffer += text
        events: list[SSEEvent] = []
        while True:
            line, found = self._next_line()
            if not found:
                break
            event = self._process_line(line)
            if event:
                events.append(event)
        return events

    def _next_line(self) -> tuple[str, bool]:
        for i, char in enumerate(self._buffer):
            if char == "\n":
                line, self._buffer = self._buffer[:i], self._buffer[i + 1:]
                return line, True
            if char == "\r":
                if i + 1 == len(self._buffer):
                    return "", False  # might be the first half of CRLF
                skip = 2 if self._buffer[i + 1] == "\n" else 1
                line, self._buffer = self._buffer[:i], self._buffer[i + skip:]
                return line, True
        return "", False

    def _process_line(self, line: str) -> SSEEvent | None:
        if line == "":
            if not self._data:
                self._event = ""
                return None
            event = SSEEvent(self._event or "message", "\n".join(self._data), self._id)
            self._event, self._data = "", []
            return event
        if line.startswith(":"):
            return None
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "data":
            self._data.append(value)
        elif name == "event":
            self._event = value
        elif name == "id":
            self._id = value
        return None
