from mcphawk.capture.http1 import Http1Stream, looks_like_request, looks_like_response
from mcphawk.capture.sse import SSEParser


def test_sse_basic_and_multiline():
    parser = SSEParser()
    events = parser.feed(b"event: endpoint\ndata: /messages?x=1\n\ndata: a\ndata: b\nid: 7\n\n")
    assert [(e.event, e.data, e.id) for e in events] == [
        ("endpoint", "/messages?x=1", None), ("message", "a\nb", "7")]


def test_sse_split_chunks_crlf_cr_and_comments():
    parser = SSEParser()
    assert parser.feed(b": keepalive\r\ndata: {\"a\"") == []
    assert parser.feed(b": 1}\r") == []
    events = parser.feed(b"\n\r\ndata:x\r\r\n\n")
    assert [e.data for e in events] == ['{"a": 1}', "x"]
    assert parser.feed("event: only\n\n") == []  # no data -> no event


def test_sse_split_utf8_sequence():
    parser = SSEParser()
    payload = "data: héllo\n\n".encode()
    cut = payload.index(b"\xc3") + 1
    assert parser.feed(payload[:cut]) == []
    assert parser.feed(payload[cut:])[0].data == "héllo"


def test_sse_field_without_space():
    events = SSEParser().feed("data:no-space\nunknown: x\n\n")
    assert events[0].data == "no-space"


class Collector:
    def __init__(self, is_response):
        self.messages = []
        self.stream = Http1Stream(is_response, self.head, self.data, self.end)
        self.current = None

    def head(self, start, headers):
        self.current = {"start": start, "headers": headers, "body": b""}

    def data(self, chunk):
        self.current["body"] += chunk

    def end(self):
        self.messages.append(self.current)


def test_http1_content_length_split_across_feeds():
    c = Collector(False)
    raw = b"POST /mcp HTTP/1.1\r\nContent-Length: 11\r\nMcp-Method: x\r\n\r\nhello world"
    for i in range(0, len(raw), 7):
        c.stream.feed(raw[i:i + 7])
    assert c.messages[0]["body"] == b"hello world"
    assert c.messages[0]["headers"]["Mcp-Method"] == "x"


def test_http1_chunked_with_extensions_and_trailers():
    c = Collector(True)
    c.stream.feed(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                  b"5;ext=1\r\nhello\r\n6\r\n world\r\n0\r\nX-T: 1\r\n\r\n"
                  b"HTTP/1.1 204 No Content\r\n\r\n")
    assert [m["body"] for m in c.messages] == [b"hello world", b""]


def test_http1_until_close_and_no_body_request():
    c = Collector(True)
    c.stream.feed(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\ndata: 1\n\n")
    c.stream.feed(b"data: 2\n\n")
    assert c.messages == []
    c.stream.close()
    assert c.messages[0]["body"] == b"data: 1\n\ndata: 2\n\n"
    r = Collector(False)
    r.stream.feed(b"GET /sse HTTP/1.1\r\nAccept: text/event-stream\r\n\r\n")
    assert r.messages[0]["body"] == b""
    c.stream.close()  # closing when idle is a no-op
    assert len(c.messages) == 1


def test_http1_zero_length_and_broken_inputs():
    c = Collector(True)
    c.stream.feed(b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n\r\n")
    assert c.messages[0]["body"] == b""
    bad = Collector(True)
    bad.stream.feed(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n")
    assert bad.stream.broken
    bad.stream.feed(b"more")
    worse = Collector(True)
    worse.stream.feed(b"HTTP/1.1 200 OK\r\nContent-Length: nope\r\n\r\n")
    assert worse.stream.broken
    huge = Collector(True)
    huge.stream.feed(b"X" * (65 * 1024))
    assert huge.stream.broken


def test_request_response_sniffing_helpers():
    assert looks_like_request(b"POST /mcp HTTP/1.1")
    assert not looks_like_request(b"HTTP/1.1 200")
    assert looks_like_response(b"HTTP/1.1 200 OK")
