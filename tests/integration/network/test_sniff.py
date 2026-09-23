import json

from scapy.all import IP, TCP, IPv6, Raw

from mcphawk.capture.sniff import FIN, SYN, Sniffer, _Direction, default_interface
from mcphawk.query import Query
from tests.traffic import modern_meta, server_meta

CLIENT = ("127.0.0.1", 51000)
SERVER = ("127.0.0.1", 3000)


class Wire:
    """Plays both sides of one TCP connection into a sniffer."""

    def __init__(self, sniffer, client=CLIENT, server=SERVER):
        self.sniffer, self.client, self.server = sniffer, client, server
        self.seq = {client: 1000, server: 5000}
        sniffer.process(client, server, 999, SYN, b"")
        sniffer.process(server, client, 4999, SYN, b"")

    def send(self, src, data, chunk=None):
        dst = self.server if src == self.client else self.client
        chunk = chunk or len(data) or 1
        for i in range(0, len(data), chunk):
            part = data[i:i + chunk]
            self.sniffer.process(src, dst, self.seq[src], 0, part)
            self.seq[src] += len(part)

    def close(self):
        self.sniffer.process(self.client, self.server, self.seq[self.client], FIN, b"")


def post(body, headers=""):
    data = json.dumps(body).encode()
    return (f"POST /mcp HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
            f"{headers}Content-Length: {len(data)}\r\n\r\n").encode() + data


def json_response(body, headers=""):
    data = json.dumps(body).encode()
    return (f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n{headers}"
            f"Content-Length: {len(data)}\r\n\r\n").encode() + data


def chunked_sse(*bodies):
    out = b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\n\r\n"
    for body in bodies:
        event = f"data: {json.dumps(body)}\r\n\r\n".encode()
        out += f"{len(event):x}\r\n".encode() + event + b"\r\n"
    return out + b"0\r\n\r\n"


def test_modern_json_and_chunked_sse(recorder, db):
    sniffer = Sniffer(recorder)
    wire = Wire(sniffer)
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": modern_meta()}}
    wire.send(CLIENT, post(listing, "Mcp-Method: tools/list\r\n"), chunk=17)
    wire.send(SERVER, json_response({"jsonrpc": "2.0", "id": 1, "result": {
        "resultType": "complete", "tools": [], "_meta": server_meta("snf")}}), chunk=23)
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "t", "_meta": modern_meta()}}
    wire.send(CLIENT, post(call))
    wire.send(SERVER, chunked_sse(
        {"jsonrpc": "2.0", "method": "notifications/progress", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "result": {"resultType": "complete", "content": []}}),
        chunk=11)
    wire.close()

    q = Query(db)
    [session] = q.list_sessions()
    assert session["capture"] == "sniff"
    assert session["target"] == "http://127.0.0.1:3000/mcp"
    assert session["server_name"] == "snf"
    detail = q.get_session(session["id"])
    assert [e["status"] for e in detail["exchanges"]] == ["ok", "ok"]
    assert detail["notification_count"] == 1
    request = q.get_message(detail["exchanges"][0]["request_msg_id"])
    assert request["headers"]["Mcp-Method"] == "tools/list"
    q.close()


def test_out_of_order_and_retransmitted_segments(recorder, db):
    sniffer = Sniffer(recorder)
    wire = Wire(sniffer)
    data = post({"jsonrpc": "2.0", "id": 7, "method": "ping"})
    start = wire.seq[CLIENT]
    a, b, c = data[:30], data[30:60], data[60:]
    sniffer.process(CLIENT, SERVER, start + 60, 0, c)
    sniffer.process(CLIENT, SERVER, start, 0, a)
    sniffer.process(CLIENT, SERVER, start, 0, a)  # full retransmit, dropped
    sniffer.process(CLIENT, SERVER, start + 20, 0, a[20:] + b)  # partial overlap
    q = Query(db)
    [exchange] = q.exchanges()
    assert exchange["method"] == "ping"
    q.close()


def test_legacy_http_sse_and_session_header(recorder, db):
    sniffer = Sniffer(recorder)
    stream = Wire(sniffer, client=("127.0.0.1", 51001))
    stream.send(stream.client, b"GET /sse HTTP/1.1\r\nAccept: text/event-stream\r\n\r\n")
    stream.send(SERVER, b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n"
                b"event: endpoint\ndata: /messages?session_id=s1\n\n")
    posts = Wire(sniffer, client=("127.0.0.1", 51002))
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    posts.send(posts.client, b"POST /messages?session_id=s1 HTTP/1.1\r\nContent-Length: "
               + str(len(body)).encode() + b"\r\n\r\n" + body)
    posts.send(SERVER, b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n\r\n")
    stream.send(SERVER, b'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'
                b"data: not json\n\n")
    stream.close()

    init = Wire(sniffer, client=("127.0.0.1", 51003))
    init.send(init.client, post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "clientInfo": {"name": "c", "version": "1"}}}))
    init.send(SERVER, json_response({"jsonrpc": "2.0", "id": 0, "result": {
        "serverInfo": {"name": "legacy", "version": "1"}}}, "Mcp-Session-Id: abc\r\n"))
    init.send(init.client, post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                "Mcp-Session-Id: abc\r\n"))
    init.send(SERVER, json_response({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}))
    get = Wire(sniffer, client=("127.0.0.1", 51004))
    get.send(get.client, b"GET /mcp HTTP/1.1\r\nMcp-Session-Id: abc\r\n\r\n")
    get.send(SERVER, b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n"
             b'data: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}\n\n')

    q = Query(db)
    sessions = {s["transport"]: s for s in q.list_sessions()}
    assert sessions["http_sse"]["exchange_count"] == 1
    assert q.get_session(sessions["http_sse"]["id"])["exchanges"][0]["status"] == "ok"
    modern = q.get_session(sessions["streamable_http"]["id"])
    assert modern["server_name"] == "legacy"
    assert len(modern["exchanges"]) == 2
    assert modern["notification_count"] == 1
    q.close()


def test_raw_json_over_tcp_and_non_mcp_traffic(recorder, db):
    sniffer = Sniffer(recorder, excluded_ports={9999})
    raw = Wire(sniffer, client=("::1", 40000), server=("::1", 7000))
    raw.send(raw.client, b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n')
    raw.send(raw.server, b'{"jsonrpc":"2.0","id":1,"result":{}}\n{"not":"rpc"}\n')
    raw.close()
    other = Wire(sniffer, client=("127.0.0.1", 40001), server=("127.0.0.1", 22))
    other.send(other.client, b"SSH-2.0-OpenSSH\r\n")
    web = Wire(sniffer, client=("127.0.0.1", 40002))
    web.send(web.client, b"GET / HTTP/1.1\r\n\r\n")
    web.send(SERVER, b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi")
    web.send(web.client, b"POST /x HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}")
    orphan = Wire(sniffer, client=("127.0.0.1", 40003))
    orphan.send(SERVER, b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
    sniffer.process(("127.0.0.1", 1), ("127.0.0.1", 9999), 1, 0, b"{}")
    sniffer.process(("127.0.0.1", 2), ("127.0.0.1", 3), 1, 0, b"")  # bare ACK

    q = Query(db)
    [session] = q.list_sessions()
    assert session["target"] == "tcp://::1:7000"
    assert session["transport"] == "unknown"
    assert session["exchange_count"] == 1
    q.close()


def test_parse_errors_drop_the_connection(recorder, monkeypatch):
    sniffer = Sniffer(recorder)
    wire = Wire(sniffer)

    def explode(*_):
        raise RuntimeError("bad")

    monkeypatch.setattr("mcphawk.capture.sniff._Connection.packet", explode)
    wire.send(CLIENT, b"x")
    assert sniffer._connections == {}


def test_handle_packet_with_scapy_layers(recorder, db):
    sniffer = Sniffer(recorder)
    body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n'
    sniffer.handle_packet(IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=5, dport=6, seq=1) / Raw(body))
    sniffer.handle_packet(IPv6(src="::1", dst="::2") / TCP(sport=5, dport=6, seq=1))
    sniffer.handle_packet(IP() / Raw(b"no tcp"))
    q = Query(db)
    assert len(q.exchanges()) == 1
    q.close()


def test_direction_wraps_sequence_numbers():
    d = _Direction()
    assert d.accept(2**32 - 2, b"abcd", syn=False) == [b"abcd"]
    assert d.next_seq == 2
    assert d.accept(2, b"ef", syn=False) == [b"ef"]


def test_default_interface():
    assert default_interface() in ("lo0", None)
