"""Incremental HTTP/1.x parser for one direction of a TCP connection."""

from collections.abc import Callable

HEAD, LENGTH, CHUNK_SIZE, CHUNK_DATA, CHUNK_END, TRAILERS, UNTIL_CLOSE = range(7)

MAX_HEAD = 64 * 1024

REQUEST_METHODS = (b"GET ", b"POST ", b"PUT ", b"DELETE ", b"PATCH ", b"OPTIONS ", b"HEAD ")


def looks_like_request(data: bytes) -> bool:
    return data.startswith(REQUEST_METHODS)


def looks_like_response(data: bytes) -> bool:
    return data.startswith(b"HTTP/1.")


class Http1Stream:
    """Feed bytes in order; receive head/data/end callbacks per message.

    ``is_response`` controls body framing rules: a response without
    Content-Length or chunked encoding runs until the connection closes
    (typical for SSE), while such a request has no body.
    """

    def __init__(
        self,
        is_response: bool,
        on_head: Callable[[str, dict[str, str]], None],
        on_data: Callable[[bytes], None],
        on_end: Callable[[], None],
    ):
        self.is_response = is_response
        self._on_head = on_head
        self._on_data = on_data
        self._on_end = on_end
        self._state = HEAD
        self._buffer = b""
        self._remaining = 0
        self.broken = False

    def feed(self, data: bytes) -> None:
        if self.broken:
            return
        self._buffer += data
        while self._buffer and not self.broken:
            if not self._step():
                break

    def close(self) -> None:
        if self._state == UNTIL_CLOSE:
            self._state = HEAD
            self._on_end()

    def _step(self) -> bool:
        """Consume what the current state can; False when more data is needed."""
        if self._state == HEAD:
            end = self._buffer.find(b"\r\n\r\n")
            if end < 0:
                if len(self._buffer) > MAX_HEAD:
                    self.broken = True
                return False
            head, self._buffer = self._buffer[:end].decode("latin-1"), self._buffer[end + 4:]
            self._start_message(head)
            return True
        if self._state == LENGTH:
            take = self._buffer[:self._remaining]
            self._buffer = self._buffer[len(take):]
            self._remaining -= len(take)
            if take:
                self._on_data(take)
            if self._remaining == 0:
                self._finish()
            return bool(self._buffer) or self._remaining == 0
        if self._state == UNTIL_CLOSE:
            self._on_data(self._buffer)
            self._buffer = b""
            return False
        if self._state in (CHUNK_SIZE, CHUNK_END, TRAILERS):
            end = self._buffer.find(b"\r\n")
            if end < 0:
                return False
            line, self._buffer = self._buffer[:end], self._buffer[end + 2:]
            if self._state == CHUNK_END:
                self._state = CHUNK_SIZE
            elif self._state == TRAILERS:
                if not line:
                    self._finish()
            else:
                try:
                    size = int(line.split(b";")[0].strip(), 16)
                except ValueError:
                    self.broken = True
                    return False
                if size == 0:
                    self._state = TRAILERS
                else:
                    self._remaining = size
                    self._state = CHUNK_DATA
            return True
        # CHUNK_DATA
        take = self._buffer[:self._remaining]
        self._buffer = self._buffer[len(take):]
        self._remaining -= len(take)
        if take:
            self._on_data(take)
        if self._remaining == 0:
            self._state = CHUNK_END
            return True
        return False

    def _start_message(self, head: str) -> None:
        lines = head.split("\r\n")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            name, sep, value = line.partition(":")
            if sep:
                headers[name.strip()] = value.strip()
        self._on_head(lines[0], headers)
        lowered = {k.lower(): v for k, v in headers.items()}
        status = 0
        if self.is_response:
            parts = lines[0].split(" ")
            status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if "chunked" in lowered.get("transfer-encoding", "").lower():
            self._state = CHUNK_SIZE
        elif "content-length" in lowered:
            try:
                self._remaining = int(lowered["content-length"])
            except ValueError:
                self.broken = True
                return
            self._state = LENGTH
            if self._remaining == 0:
                self._finish()
        elif self.is_response and not (100 <= status < 200 or status in (204, 304)):
            self._state = UNTIL_CLOSE
        else:
            self._finish()

    def _finish(self) -> None:
        self._state = HEAD
        self._on_end()
