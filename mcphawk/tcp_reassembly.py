"""TCP stream reassembly for capturing complete HTTP/SSE responses."""

import logging
from typing import Optional

from scapy.all import IP, TCP, IPv6, Raw

logger = logging.getLogger(__name__)


class StreamKey:
    """Key for identifying TCP streams."""

    def __init__(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int):
        # Always order the tuple consistently (lower IP/port first)
        if (src_ip, src_port) < (dst_ip, dst_port):
            self.key = (src_ip, src_port, dst_ip, dst_port)
        else:
            self.key = (dst_ip, dst_port, src_ip, src_port)

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return self.key == other.key

    def __repr__(self):
        return f"StreamKey{self.key}"


class HTTPStream:
    """Tracks HTTP request/response pairs in a TCP stream."""

    def __init__(self):
        self.pending_request: Optional[bytes] = None
        self.pending_response: Optional[bytes] = None
        self.response_headers: Optional[dict[str, str]] = None
        self.content_length: Optional[int] = None
        self.is_chunked: bool = False
        self.is_sse: bool = False
        self.buffer: bytes = b""

    def add_request(self, data: bytes):
        """Add HTTP request data."""
        self.pending_request = data
        self.buffer = b""
        logger.debug(f"New HTTP request: {data[:100]}")

    def add_response_data(self, data: bytes):
        """Add HTTP response data, handling headers and body."""
        self.buffer += data

        # If we don't have headers yet, try to parse them
        if self.response_headers is None and b"\r\n\r\n" in self.buffer:
            header_end = self.buffer.find(b"\r\n\r\n") + 4
            header_data = self.buffer[:header_end].decode('utf-8', errors='ignore')
            self.buffer = self.buffer[header_end:]  # Keep only body in buffer

            # Parse headers
            lines = header_data.split('\r\n')
            self.response_headers = {}
            for line in lines[1:]:  # Skip status line
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    self.response_headers[key.lower()] = value

            # Check for SSE
            content_type = self.response_headers.get('content-type', '')
            self.is_sse = 'text/event-stream' in content_type

            # Check for chunked encoding
            transfer_encoding = self.response_headers.get('transfer-encoding', '')
            self.is_chunked = 'chunked' in transfer_encoding

            # Get content length if not chunked
            if not self.is_chunked and 'content-length' in self.response_headers:
                self.content_length = int(self.response_headers['content-length'])

            logger.debug(f"Response headers parsed: SSE={self.is_sse}, chunked={self.is_chunked}")

    def extract_sse_messages(self) -> list[str]:
        """Extract complete SSE messages from buffer."""
        messages = []

        # SSE messages are separated by double newlines
        while b"\n\n" in self.buffer:
            msg_end = self.buffer.find(b"\n\n") + 2
            msg_data = self.buffer[:msg_end].decode('utf-8', errors='ignore')
            self.buffer = self.buffer[msg_end:]

            # Extract data lines
            for line in msg_data.split('\n'):
                if line.startswith('data: '):
                    json_data = line[6:].strip()
                    if json_data and json_data.startswith('{'):
                        messages.append(json_data)
                        logger.debug(f"Extracted SSE message: {json_data[:100]}")

        return messages

    def extract_chunked_data(self) -> Optional[bytes]:
        """Extract data from chunked transfer encoding."""
        # This is a simplified implementation
        # Real chunked parsing is more complex
        complete_data = b""

        while True:
            # Find chunk size
            if b"\r\n" not in self.buffer:
                break

            size_end = self.buffer.find(b"\r\n")
            try:
                chunk_size = int(self.buffer[:size_end], 16)
            except ValueError:
                break

            if chunk_size == 0:
                # Last chunk
                return complete_data

            # Check if we have the full chunk
            chunk_start = size_end + 2
            chunk_end = chunk_start + chunk_size + 2  # +2 for trailing \r\n

            if len(self.buffer) < chunk_end:
                # Need more data
                break

            complete_data += self.buffer[chunk_start:chunk_start + chunk_size]
            self.buffer = self.buffer[chunk_end:]

        return None  # Not complete yet


class TCPStreamReassembler:
    """Reassembles TCP streams to capture complete HTTP messages."""

    def __init__(self):
        self.streams: dict[StreamKey, HTTPStream] = {}

    def process_packet(self, pkt) -> list[dict]:
        """Process a packet and return any complete messages."""
        messages = []

        # Only process TCP packets with data
        if not pkt.haslayer(TCP) or not pkt.haslayer(Raw):
            return messages

        # Debug: Log that we're processing a packet
        if pkt.haslayer(Raw):
            payload = bytes(pkt[Raw])
            if len(payload) > 0:
                logger.debug(f"TCP reassembly: Processing packet with {len(payload)} bytes, starts with: {payload[:20]}")

        # Get stream key
        if pkt.haslayer(IP):
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
        elif pkt.haslayer(IPv6):
            src_ip = pkt[IPv6].src
            dst_ip = pkt[IPv6].dst
        else:
            return messages

        src_port = pkt[TCP].sport
        dst_port = pkt[TCP].dport
        payload = bytes(pkt[Raw])

        # Create stream key
        stream_key = StreamKey(src_ip, src_port, dst_ip, dst_port)

        # Get or create stream
        if stream_key not in self.streams:
            self.streams[stream_key] = HTTPStream()
        stream = self.streams[stream_key]

        # Check if this is an HTTP request
        if payload.startswith(b"POST ") or payload.startswith(b"GET "):
            stream.add_request(payload)
            logger.debug(f"TCP reassembly: HTTP request on {src_port}->{dst_port}")

        # Check if this is an HTTP response or continuation
        elif payload.startswith(b"HTTP/1.") or stream.response_headers is not None:
            stream.add_response_data(payload)
            logger.debug(f"TCP reassembly: HTTP response data on {src_port}->{dst_port}, SSE={stream.is_sse}, buffer_len={len(stream.buffer)}")

            # Try to extract messages if this is SSE
            if stream.is_sse:
                sse_messages = stream.extract_sse_messages()
                logger.debug(f"TCP reassembly: Extracted {len(sse_messages)} SSE messages")
                for msg in sse_messages:
                    messages.append({
                        "src_ip": src_ip,
                        "src_port": src_port,
                        "dst_ip": dst_ip,
                        "dst_port": dst_port,
                        "message": msg,
                        "type": "sse_response"
                    })

        # Check for standalone SSE data (no HTTP headers)
        elif payload.startswith(b"data: ") and b"jsonrpc" in payload:
            # This might be a continuation of an SSE stream
            logger.debug(f"TCP reassembly: Standalone SSE data on {src_port}->{dst_port}")
            stream.buffer = payload
            sse_messages = stream.extract_sse_messages()
            for msg in sse_messages:
                messages.append({
                    "src_ip": src_ip,
                    "src_port": src_port,
                    "dst_ip": dst_ip,
                    "dst_port": dst_port,
                    "message": msg,
                    "type": "sse_data"
                })

        # For any packet, if we have an SSE stream, try to process it
        elif stream.is_sse and len(payload) > 0:
            # This could be a continuation of SSE data
            logger.debug(f"TCP reassembly: Possible SSE continuation on {src_port}->{dst_port}, payload: {payload[:50]}")
            stream.buffer += payload
            sse_messages = stream.extract_sse_messages()
            if sse_messages:
                logger.debug(f"TCP reassembly: Found {len(sse_messages)} messages in continuation")
            for msg in sse_messages:
                messages.append({
                    "src_ip": src_ip,
                    "src_port": src_port,
                    "dst_ip": dst_ip,
                    "dst_port": dst_port,
                    "message": msg,
                    "type": "sse_continuation"
                })

        return messages

    def cleanup_old_streams(self, timeout: int = 300):
        """Remove old streams to prevent memory leaks."""
        # TODO: Implement timeout-based cleanup
        pass
