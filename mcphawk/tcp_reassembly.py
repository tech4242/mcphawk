"""TCP stream reassembly for capturing complete HTTP/SSE responses."""

import logging
from typing import Optional

from scapy.all import IP, TCP, IPv6, Raw

from .transport_detector import (
    MCPTransport,
    TransportTracker,
    detect_transport_from_http,
    extract_endpoint_from_sse,
)

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
        self.request_method: Optional[str] = None
        self.request_path: Optional[str] = None
        self.request_headers: dict[str, str] = {}
        self.detected_transport: MCPTransport = MCPTransport.UNKNOWN

    def add_request(self, data: bytes):
        """Add HTTP request data and parse headers."""
        self.pending_request = data
        self.buffer = b""
        logger.debug(f"New HTTP request: {data[:100]}")

        # Parse request line and headers
        try:
            request_str = data.decode('utf-8', errors='ignore')
            lines = request_str.split('\r\n')
            if lines:
                # Parse request line
                parts = lines[0].split(' ')
                if len(parts) >= 2:
                    self.request_method = parts[0]
                    self.request_path = parts[1]

                # Parse headers
                self.request_headers = {}
                for line in lines[1:]:
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        self.request_headers[key.lower()] = value
                    elif line == '':
                        break  # End of headers

                # Try to detect transport type from request alone
                if self.request_method and self.request_path:
                    self.detected_transport = detect_transport_from_http(
                        self.request_method,
                        self.request_path,
                        self.request_headers,
                        False  # No response yet
                    )
                    logger.debug(f"Transport detected from request: {self.detected_transport}")
        except Exception as e:
            logger.debug(f"Error parsing request: {e}")

    def add_response_data(self, data: bytes):
        """Add HTTP response data, handling headers and body."""
        self.buffer += data
        logger.debug(f"HTTPStream: Added {len(data)} bytes to buffer, total buffer size: {len(self.buffer)}")

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

            # Try to detect transport type
            if self.request_method and self.request_path:
                self.detected_transport = detect_transport_from_http(
                    self.request_method,
                    self.request_path,
                    self.request_headers,
                    self.is_sse
                )

    def extract_sse_messages(self) -> list[str]:
        """Extract complete SSE messages from buffer."""
        messages = []
        logger.debug(f"extract_sse_messages called, buffer size: {len(self.buffer)}, is_chunked: {self.is_chunked}")
        if self.buffer:
            logger.debug(f"Buffer content preview: {self.buffer[:100]}")

        # If chunked encoding, we need to handle chunk sizes
        data_to_process = self.buffer
        if self.is_chunked and self.buffer:
            # Try to extract chunks
            logger.debug("Attempting to extract chunks from buffer")
            chunk_data = self.extract_chunked_data()
            if chunk_data:
                # Process the extracted chunk data, but don't replace the buffer
                # The buffer still contains any remaining chunk data
                data_to_process = chunk_data
                logger.debug(f"Extracted {len(chunk_data)} bytes from chunks to process")
            else:
                logger.debug("No complete chunks extracted yet")
                return messages  # Wait for more data

        # SSE messages are separated by double newlines (could be \r\n\r\n or \n\n)
        logger.debug(f"Looking for SSE messages in {len(data_to_process)} bytes of data")

        # Look for either \r\n\r\n or \n\n
        while b"\r\n\r\n" in data_to_process or b"\n\n" in data_to_process:
            # Find the first occurrence of either separator
            crlf_pos = data_to_process.find(b"\r\n\r\n")
            lf_pos = data_to_process.find(b"\n\n")

            if crlf_pos >= 0 and (lf_pos < 0 or crlf_pos < lf_pos):
                msg_end = crlf_pos + 4  # +4 for \r\n\r\n
            else:
                msg_end = lf_pos + 2  # +2 for \n\n

            msg_data = data_to_process[:msg_end].decode('utf-8', errors='ignore')
            data_to_process = data_to_process[msg_end:]
            logger.debug(f"Found SSE message block: {msg_data[:100]!r}")

            # Check for endpoint event (HTTP+SSE transport)
            if "event: endpoint" in msg_data:
                endpoint_url = extract_endpoint_from_sse(msg_data)
                if endpoint_url:
                    logger.debug(f"Found endpoint event, URL: {endpoint_url}")
                    self.detected_transport = MCPTransport.HTTP_SSE

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
        original_buffer = self.buffer

        while True:
            # Find chunk size
            if b"\r\n" not in self.buffer:
                logger.debug("extract_chunked_data: No CRLF in buffer, need more data")
                break

            size_end = self.buffer.find(b"\r\n")
            chunk_size_str = self.buffer[:size_end].decode('utf-8', errors='ignore').strip()
            logger.debug(f"extract_chunked_data: Chunk size string: '{chunk_size_str}'")

            try:
                chunk_size = int(chunk_size_str, 16)
                logger.debug(f"extract_chunked_data: Parsed chunk size: {chunk_size}")
            except ValueError:
                logger.debug("extract_chunked_data: Failed to parse chunk size")
                break

            if chunk_size == 0:
                # Last chunk - consume it from buffer
                self.buffer = self.buffer[size_end + 4:]  # Skip "0\r\n\r\n"
                logger.debug(f"extract_chunked_data: Found last chunk (size 0), returning {len(complete_data)} bytes")
                return complete_data if complete_data else None

            # Check if we have the full chunk
            chunk_start = size_end + 2
            chunk_end = chunk_start + chunk_size + 2  # +2 for trailing \r\n

            if len(self.buffer) < chunk_end:
                # Need more data - restore original buffer and return what we have so far
                logger.debug(f"extract_chunked_data: Need more data, have {len(self.buffer)}, need {chunk_end}")
                self.buffer = original_buffer
                break

            chunk_data = self.buffer[chunk_start:chunk_start + chunk_size]
            logger.debug(f"extract_chunked_data: Extracted chunk of {len(chunk_data)} bytes")
            complete_data += chunk_data
            self.buffer = self.buffer[chunk_end:]

        if complete_data:
            logger.debug(f"extract_chunked_data: Returning {len(complete_data)} bytes of unchunked data")
            return complete_data
        return None  # Not complete yet


class TCPStreamReassembler:
    """Reassembles TCP streams to capture complete HTTP messages."""

    def __init__(self):
        self.streams: dict[StreamKey, HTTPStream] = {}
        self.transport_tracker = TransportTracker()

    def process_packet(self, pkt) -> list[dict]:
        """Process a packet and return any complete messages."""
        messages = []

        # Only process TCP packets with data
        if not pkt.haslayer(TCP) or not pkt.haslayer(Raw):
            return messages

        tcp = pkt[TCP]

        # Debug: Log that we're processing a packet
        if pkt.haslayer(Raw):
            payload = bytes(pkt[Raw])
            if len(payload) > 0 and (tcp.sport == 8765 or tcp.dport == 8765):
                logger.debug(f"TCP reassembly: Processing {tcp.sport}->{tcp.dport} packet with {len(payload)} bytes")
                logger.debug(f"TCP reassembly: Packet content: {payload[:100]}")

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

        # Debug stream key for port 8765
        if src_port == 8765 or dst_port == 8765:
            logger.debug(f"TCP reassembly: Stream key for port 8765: {stream_key}")

        # Get or create stream
        if stream_key not in self.streams:
            self.streams[stream_key] = HTTPStream()
            logger.debug(f"TCP reassembly: Created new stream for {stream_key}")
        stream = self.streams[stream_key]

        # Check if this is an HTTP request
        if payload.startswith(b"POST ") or payload.startswith(b"GET "):
            stream.add_request(payload)
            logger.debug(f"TCP reassembly: HTTP request on {src_port}->{dst_port}")
            logger.debug(f"TCP reassembly: Request method: {stream.request_method}, path: {stream.request_path}")
            logger.debug(f"TCP reassembly: Request headers: {stream.request_headers}")

            # If we detected transport from request, update tracker
            if stream.detected_transport != MCPTransport.UNKNOWN:
                self.transport_tracker.update_transport(
                    src_ip, src_port, dst_ip, dst_port,
                    stream.detected_transport
                )
                logger.debug(f"TCP reassembly: Updated transport tracker with {stream.detected_transport} from request")

                # For HTTP+SSE, log detection in auto-detect mode
                if stream.detected_transport == MCPTransport.HTTP_SSE:
                    logger.info(f"[MCPHawk] Detected HTTP+SSE transport on {src_ip}:{src_port} -> {dst_ip}:{dst_port} (GET {stream.request_path} with Accept: text/event-stream)")
            else:
                logger.debug("TCP reassembly: Transport still unknown after request parsing")

        # Check if this is an HTTP response
        elif payload.startswith(b"HTTP/1."):
            stream.add_response_data(payload)
            logger.debug(f"TCP reassembly: HTTP response data on {src_port}->{dst_port}, SSE={stream.is_sse}, buffer_len={len(stream.buffer)}")
            logger.debug(f"TCP reassembly: Stream {stream_key} now has headers: {stream.response_headers}")

            # Try to extract messages if this is SSE
            if stream.is_sse:
                sse_messages = stream.extract_sse_messages()
                logger.debug(f"TCP reassembly: Extracted {len(sse_messages)} SSE messages")
                for msg in sse_messages:
                    # Update transport tracker if detected
                    if stream.detected_transport != MCPTransport.UNKNOWN:
                        self.transport_tracker.update_transport(
                            src_ip, src_port, dst_ip, dst_port,
                            stream.detected_transport
                        )

                    messages.append({
                        "src_ip": src_ip,
                        "src_port": src_port,
                        "dst_ip": dst_ip,
                        "dst_port": dst_port,
                        "message": msg,
                        "type": "sse_response",
                        "transport": stream.detected_transport.value
                    })

        # Check for standalone SSE data (no HTTP headers)
        elif payload.startswith(b"data: ") and b"jsonrpc" in payload:
            # This might be a continuation of an SSE stream
            logger.debug(f"TCP reassembly: Standalone SSE data on {src_port}->{dst_port}")
            stream.buffer = payload
            sse_messages = stream.extract_sse_messages()
            for msg in sse_messages:
                # Get transport from tracker
                transport = self.transport_tracker.get_transport(src_ip, src_port, dst_ip, dst_port)
                messages.append({
                    "src_ip": src_ip,
                    "src_port": src_port,
                    "dst_ip": dst_ip,
                    "dst_port": dst_port,
                    "message": msg,
                    "type": "sse_data",
                    "transport": transport.value
                })

        # For any packet, if we have an SSE stream, try to process it
        elif stream.response_headers is not None and stream.is_sse and len(payload) > 0:
            # This is SSE data following headers
            logger.debug(f"TCP reassembly: SSE data on tracked stream {src_port}->{dst_port}, payload preview: {payload[:50]}")
            stream.add_response_data(payload)
            sse_messages = stream.extract_sse_messages()
            if sse_messages:
                logger.debug(f"TCP reassembly: Found {len(sse_messages)} messages in SSE stream")
            for msg in sse_messages:
                # Update transport tracker if detected
                if stream.detected_transport != MCPTransport.UNKNOWN:
                    self.transport_tracker.update_transport(
                        src_ip, src_port, dst_ip, dst_port,
                        stream.detected_transport
                    )

                messages.append({
                    "src_ip": src_ip,
                    "src_port": src_port,
                    "dst_ip": dst_ip,
                    "dst_port": dst_port,
                    "message": msg,
                    "type": "sse_continuation",
                    "transport": stream.detected_transport.value
                })

        # Catch-all: Handle any data on a stream where we've seen headers
        elif len(payload) > 0:
            logger.debug(f"TCP reassembly: Catch-all for {src_port}->{dst_port}")
            # Check if this stream has headers and might be waiting for body data
            if stream.response_headers is not None:
                logger.debug(f"TCP reassembly: Data on stream with headers {src_port}->{dst_port}, is_sse={stream.is_sse}")
                logger.debug(f"TCP reassembly: Data preview: {payload[:50]}")

                # Add data to the stream
                stream.add_response_data(payload)

                # If it's an SSE stream, try to extract messages
                if stream.is_sse:
                    logger.debug(f"TCP reassembly: Processing SSE stream, buffer now has {len(stream.buffer)} bytes")
                    sse_messages = stream.extract_sse_messages()
                    logger.debug(f"TCP reassembly: Extracted {len(sse_messages)} SSE messages from continuation")
                    for msg in sse_messages:
                        messages.append({
                            "src_ip": src_ip,
                            "src_port": src_port,
                            "dst_ip": dst_ip,
                            "dst_port": dst_port,
                            "message": msg,
                            "type": "sse_continuation"
                        })
            elif src_port == 8765 or dst_port == 8765:
                logger.debug(f"TCP reassembly: Unhandled packet {src_port}->{dst_port}, no headers yet")
                logger.debug(f"TCP reassembly: Payload starts with: {payload[:50]}")

        return messages

    def cleanup_old_streams(self, timeout: int = 300):
        """Remove old streams to prevent memory leaks."""
        # TODO: Implement timeout-based cleanup
        pass
