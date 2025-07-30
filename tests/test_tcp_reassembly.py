"""Tests for TCP stream reassembly and SSE parsing."""

from scapy.all import IP, TCP, Ether, Raw

from mcphawk.tcp_reassembly import HTTPStream, TCPStreamReassembler


class TestHTTPStream:
    """Test HTTPStream parsing."""

    def test_extract_sse_messages_with_lf_separator(self):
        """Test SSE message extraction with LF separator (\n\n)."""
        stream = HTTPStream()
        stream.is_sse = True
        stream.is_chunked = False
        stream.response_headers = {"content-type": "text/event-stream"}

        # Add SSE data with LF separator
        stream.buffer = b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'

        messages = stream.extract_sse_messages()
        assert len(messages) == 1
        assert messages[0] == '{"jsonrpc":"2.0","id":1,"result":{}}'

    def test_extract_sse_messages_with_crlf_separator(self):
        """Test SSE message extraction with CRLF separator (\r\n\r\n)."""
        stream = HTTPStream()
        stream.is_sse = True
        stream.is_chunked = False
        stream.response_headers = {"content-type": "text/event-stream"}

        # Add SSE data with CRLF separator (common with HTTP)
        stream.buffer = b'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\r\n\r\n'

        messages = stream.extract_sse_messages()
        assert len(messages) == 1
        assert messages[0] == '{"jsonrpc":"2.0","id":1,"result":{}}'

    def test_extract_sse_messages_mixed_separators(self):
        """Test SSE message extraction with mixed separators."""
        stream = HTTPStream()
        stream.is_sse = True
        stream.is_chunked = False
        stream.response_headers = {"content-type": "text/event-stream"}

        # Multiple messages with different separators
        stream.buffer = (
            b'event: message\ndata: {"id":1}\n\n'  # LF separator
            b'event: message\r\ndata: {"id":2}\r\n\r\n'  # CRLF separator
        )

        messages = stream.extract_sse_messages()
        assert len(messages) == 2
        assert messages[0] == '{"id":1}'
        assert messages[1] == '{"id":2}'

    def test_extract_sse_messages_with_chunked_encoding(self):
        """Test SSE message extraction from chunked transfer encoding."""
        stream = HTTPStream()
        stream.is_sse = True
        stream.is_chunked = True
        stream.response_headers = {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked"
        }

        # Chunked data: size in hex, CRLF, data, CRLF
        sse_data = b'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\r\n\r\n'
        chunk_size = hex(len(sse_data))[2:].encode()
        stream.buffer = chunk_size + b'\r\n' + sse_data + b'\r\n0\r\n\r\n'

        messages = stream.extract_sse_messages()
        assert len(messages) == 1
        assert messages[0] == '{"jsonrpc":"2.0","id":1,"result":{}}'

    def test_extract_sse_messages_incomplete_chunk(self):
        """Test SSE message extraction with incomplete chunked data."""
        stream = HTTPStream()
        stream.is_sse = True
        stream.is_chunked = True
        stream.response_headers = {
            "content-type": "text/event-stream",
            "transfer-encoding": "chunked"
        }

        # Incomplete chunk - missing data
        stream.buffer = b'10\r\nonly5bytes'

        messages = stream.extract_sse_messages()
        assert len(messages) == 0  # Should wait for more data

    def test_parse_http_response_headers(self):
        """Test HTTP response header parsing."""
        stream = HTTPStream()

        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
        )

        stream.add_response_data(response)

        assert stream.response_headers is not None
        assert stream.is_sse is True
        assert stream.is_chunked is True
        assert stream.response_headers["content-type"] == "text/event-stream"
        assert stream.response_headers["transfer-encoding"] == "chunked"


class TestTCPStreamReassembler:
    """Test TCP stream reassembly."""

    def test_http_request_response_flow(self):
        """Test complete HTTP request/response flow."""
        reassembler = TCPStreamReassembler()

        # HTTP request
        req_pkt = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=12345, dport=8765) / Raw(
            b"POST /mcp HTTP/1.1\r\n"
            b"Content-Type: application/json\r\n"
            b"\r\n"
            b'{"jsonrpc":"2.0","method":"test","id":1}'
        )

        messages = reassembler.process_packet(req_pkt)
        assert len(messages) == 0  # Requests are not returned as messages

        # HTTP response with SSE
        resp_pkt = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=8765, dport=12345) / Raw(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"\r\n"
            b'event: message\r\n'
            b'data: {"jsonrpc":"2.0","id":1,"result":"ok"}\r\n'
            b'\r\n'
        )

        messages = reassembler.process_packet(resp_pkt)
        assert len(messages) == 1
        assert messages[0]["message"] == '{"jsonrpc":"2.0","id":1,"result":"ok"}'
        assert messages[0]["type"] == "sse_response"

    def test_chunked_sse_response_reassembly(self):
        """Test reassembly of chunked SSE response across multiple packets."""
        reassembler = TCPStreamReassembler()

        # First, send request to establish stream
        req_pkt = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=12345, dport=8765) / Raw(
            b"POST /mcp HTTP/1.1\r\n\r\n"
        )
        reassembler.process_packet(req_pkt)

        # Response headers
        resp_hdr = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=8765, dport=12345) / Raw(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
        )

        messages = reassembler.process_packet(resp_hdr)
        assert len(messages) == 0  # Just headers, no data yet

        # Chunked SSE data
        sse_data = b'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":"test"}\r\n\r\n'
        chunk_size = hex(len(sse_data))[2:].encode()

        data_pkt = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=8765, dport=12345) / Raw(
            chunk_size + b'\r\n' + sse_data + b'\r\n'
        )

        messages = reassembler.process_packet(data_pkt)
        assert len(messages) == 1
        assert messages[0]["message"] == '{"jsonrpc":"2.0","id":1,"result":"test"}'

        # End chunk
        end_pkt = Ether() / IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=8765, dport=12345) / Raw(
            b"0\r\n\r\n"
        )

        messages = reassembler.process_packet(end_pkt)
        assert len(messages) == 0  # End chunk doesn't produce messages

    def test_multiple_streams(self):
        """Test handling multiple concurrent TCP streams."""
        reassembler = TCPStreamReassembler()

        # Stream 1: Client A -> Server
        req1 = Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1111, dport=8765) / Raw(
            b"POST /api HTTP/1.1\r\n\r\n"
        )
        reassembler.process_packet(req1)

        # Stream 2: Client B -> Server
        req2 = Ether() / IP(src="10.0.0.3", dst="10.0.0.2") / TCP(sport=2222, dport=8765) / Raw(
            b"POST /api HTTP/1.1\r\n\r\n"
        )
        reassembler.process_packet(req2)

        # Response to Client A
        resp1 = Ether() / IP(src="10.0.0.2", dst="10.0.0.1") / TCP(sport=8765, dport=1111) / Raw(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"\r\n"
            b'data: {"client":"A"}\r\n\r\n'
        )

        messages = reassembler.process_packet(resp1)
        assert len(messages) == 1
        assert messages[0]["message"] == '{"client":"A"}'
        assert messages[0]["dst_port"] == 1111

        # Response to Client B
        resp2 = Ether() / IP(src="10.0.0.2", dst="10.0.0.3") / TCP(sport=8765, dport=2222) / Raw(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/event-stream\r\n"
            b"\r\n"
            b'data: {"client":"B"}\r\n\r\n'
        )

        messages = reassembler.process_packet(resp2)
        assert len(messages) == 1
        assert messages[0]["message"] == '{"client":"B"}'
        assert messages[0]["dst_port"] == 2222
