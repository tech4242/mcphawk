import asyncio
import json
import logging
import platform
import uuid
from datetime import datetime, timezone

# Suppress Scapy warnings before importing
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

from scapy.all import IP, TCP, IPv6, Raw, conf, sniff  # noqa: E402

from mcphawk.logger import log_message  # noqa: E402
from mcphawk.tcp_reassembly import TCPStreamReassembler  # noqa: E402
from mcphawk.web.broadcaster import broadcast_new_log  # noqa: E402

# Set up logger for this module
logger = logging.getLogger(__name__)

# Server registry to track server names by connection
_server_registry = {}  # {connection_id: server_info}


def _get_connection_id(src_ip: str, src_port: int, dst_ip: str, dst_port: int) -> str:
    """Generate unique connection identifier for HTTP connections."""
    return f"{src_ip}:{src_port}->{dst_ip}:{dst_port}"


async def _safe_broadcast(log_entry: dict) -> None:
    try:
        await broadcast_new_log(log_entry)
    except Exception as e:
        logger.debug(f"Broadcast failed: {e}")


def _broadcast_in_any_loop(log_entry: dict) -> None:
    try:
        loop = asyncio.get_running_loop()
        _ = loop.create_task(_safe_broadcast(log_entry))  # noqa: RUF006
    except RuntimeError:
        asyncio.run(_safe_broadcast(log_entry))


# Global variable to track auto-detect mode
_auto_detect_mode = False

# Global variable to track excluded ports
_excluded_ports = set()

# TCP stream reassembler for handling SSE and chunked responses
_tcp_reassembler = TCPStreamReassembler()
logger.info("TCP stream reassembler initialized")

def packet_callback(pkt):
    """
    Callback for every sniffed packet.
    Extract JSON-RPC messages from raw TCP payloads.
    """
    # Skip packets to/from excluded ports
    if pkt.haslayer(TCP) and _excluded_ports:
        tcp_layer = pkt[TCP]
        if tcp_layer.sport in _excluded_ports or tcp_layer.dport in _excluded_ports:
            return

    # Try TCP stream reassembly first for SSE/chunked responses
    if pkt.haslayer(TCP) and pkt.haslayer(Raw):
        tcp = pkt[TCP]
        if tcp.sport == 8765 or tcp.dport == 8765:
            raw_data = bytes(pkt[Raw])
            logger.debug(f"TCP packet for reassembly: {tcp.sport}->{tcp.dport}, {len(raw_data)} bytes")
            # Log first 100 bytes to see what we're getting
            preview = raw_data[:100].decode('utf-8', errors='replace')
            logger.debug(f"Packet preview: {preview!r}")

    reassembled_messages = _tcp_reassembler.process_packet(pkt)
    if reassembled_messages:
        logger.info(f"TCP reassembler found {len(reassembled_messages)} messages!")
    elif pkt.haslayer(TCP) and pkt.haslayer(Raw):
        tcp = pkt[TCP]
        if tcp.sport == 8765 or tcp.dport == 8765:
            logger.debug(f"TCP reassembler returned no messages for {tcp.sport}->{tcp.dport}")
    for msg_info in reassembled_messages:
        # Process reassembled SSE messages
        if "jsonrpc" in msg_info["message"]:
            logger.debug(f"Reassembled {msg_info['type']}: {msg_info['message'][:100]}...")

            ts = datetime.now(tz=timezone.utc)
            log_id = str(uuid.uuid4())

            # Use transport type from TCP reassembler
            transport = msg_info.get("transport", "unknown")

            # Determine direction based on message type
            from .utils import extract_server_info
            direction = "unknown"

            # For HTTP, incoming = server->client, outgoing = client->server
            if msg_info.get("type") == "HTTP Response":
                direction = "incoming"
                # Check for server info in response
                server_info = extract_server_info(msg_info["message"])
                if server_info:
                    conn_id = _get_connection_id(
                        msg_info["dst_ip"], msg_info["dst_port"],
                        msg_info["src_ip"], msg_info["src_port"]
                    )
                    _server_registry[conn_id] = server_info
                    logger.debug(f"Captured server info for {conn_id}: {server_info}")
            else:
                direction = "outgoing"

            entry = {
                "log_id": log_id,
                "timestamp": ts,
                "src_ip": msg_info["src_ip"],
                "src_port": msg_info["src_port"],
                "dst_ip": msg_info["dst_ip"],
                "dst_port": msg_info["dst_port"],
                "direction": direction,
                "message": msg_info["message"],
                "transport_type": transport,
            }

            # Build metadata
            metadata = {}

            # Add server info if we have it
            conn_id = _get_connection_id(
                msg_info["src_ip"], msg_info["src_port"],
                msg_info["dst_ip"], msg_info["dst_port"]
            )
            if conn_id in _server_registry:
                server_info = _server_registry[conn_id]
                metadata["server_name"] = server_info["name"]
                metadata["server_version"] = server_info["version"]

            # MCPHawk's own traffic will be identified by server_name in metadata

            if metadata:
                entry["metadata"] = json.dumps(metadata)

            log_message(entry)

            # Convert timestamp to ISO only for WebSocket broadcast
            broadcast_entry = dict(entry)
            broadcast_entry["timestamp"] = ts.isoformat()
            _broadcast_in_any_loop(broadcast_entry)

            # In auto-detect mode, log when we find MCP traffic
            if _auto_detect_mode:
                transport_name = {
                    "streamable_http": "Streamable HTTP",
                    "http_sse": "HTTP+SSE",
                    "stdio": "stdio",
                    "unknown": "Unknown"
                }.get(transport, "Unknown")
                logger.info(f"Detected {transport_name} MCP traffic on port {msg_info['src_port']} -> {msg_info['dst_port']}")

    if pkt.haslayer(Raw):
        raw_payload = pkt[Raw].load

        # Check if this looks like SSE data
        if raw_payload.startswith(b"data: "):
            logger.debug(f"SSE data packet detected: {raw_payload[:100]}...")

        if not _auto_detect_mode:  # Less verbose in auto-detect mode
            logger.debug(f"Raw payload: {raw_payload[:60]}...")

        # Try to process as raw JSON-RPC or HTTP POST with JSON-RPC
        try:
            decoded = raw_payload.decode("utf-8", errors="ignore")

            # Debug log all HTTP traffic
            if decoded.startswith("HTTP/1.1"):
                logger.debug(f"HTTP Response: {decoded[:200]}...")

            # Check for standalone SSE data (not part of HTTP response)
            if decoded.startswith("data: ") and "jsonrpc" in decoded:
                # This is a standalone SSE data packet
                sse_data = decoded[6:]  # Skip "data: "
                if "\n" in sse_data:
                    sse_data = sse_data[:sse_data.index("\n")]
                if sse_data.startswith("{"):
                    logger.debug(f"Found standalone SSE data: {sse_data[:100]}...")
                    decoded = sse_data
                    # Process as regular JSON-RPC

            # Check for HTTP request/response with JSON-RPC content
            if (decoded.startswith("POST") or decoded.startswith("HTTP/1.1")) and "\r\n\r\n" in decoded:
                # Extract JSON body from HTTP request/response
                body_start = decoded.find("\r\n\r\n") + 4
                json_body = decoded[body_start:]

                # Debug log HTTP responses
                if decoded.startswith("HTTP/1.1") and "text/event-stream" in decoded:
                    logger.debug(f"SSE Response detected, body length: {len(json_body)}, body preview: {json_body[:100]}")

                # Check for Server-Sent Events (SSE) format used by MCP SDK
                if "text/event-stream" in decoded and json_body.startswith("data: "):
                    # Extract JSON from SSE format: "data: {...}\n\n"
                    sse_data = json_body[6:]  # Skip "data: "
                    if "\n" in sse_data:
                        sse_data = sse_data[:sse_data.index("\n")]
                    if sse_data.startswith("{") and "jsonrpc" in sse_data:
                        decoded = sse_data
                        logger.debug(f"Extracted JSON-RPC from SSE: {decoded[:100]}...")
                elif json_body.startswith("{") and "jsonrpc" in json_body:
                    decoded = json_body  # Use just the JSON body
                    logger.debug(f"Extracted JSON-RPC from HTTP: {decoded[:100]}...")

            # Process if we have JSON-RPC content
            if decoded.startswith("{") and "jsonrpc" in decoded:
                logger.debug(f"Sniffer captured: {decoded}")

                ts = datetime.now(tz=timezone.utc)
                src_port = pkt[TCP].sport if pkt.haslayer(TCP) else 0
                dst_port = pkt[TCP].dport if pkt.haslayer(TCP) else 0

                # In auto-detect mode, log when we find MCP traffic on a new port
                if _auto_detect_mode:
                    logger.info(f"Detected MCP traffic on port {src_port} -> {dst_port}")

                # Get IP addresses
                if pkt.haslayer(IP):
                    src_ip = pkt[IP].src
                    dst_ip = pkt[IP].dst
                elif pkt.haslayer(IPv6):
                    src_ip = pkt[IPv6].src
                    dst_ip = pkt[IPv6].dst
                else:
                    src_ip = ""
                    dst_ip = ""

                log_id = str(uuid.uuid4())

                # Check if we know the transport type for this connection
                transport = _tcp_reassembler.transport_tracker.get_transport(
                    src_ip, src_port, dst_ip, dst_port
                ).value

                if _auto_detect_mode and transport != "unknown":
                    logger.debug(f"Auto-detect: Found transport {transport} for {src_ip}:{src_port} -> {dst_ip}:{dst_port}")

                # Determine direction and check for server info
                from .utils import extract_server_info
                direction = "unknown"

                # For raw TCP, we need to infer direction
                # If it's a response (has result or error), it's incoming
                try:
                    msg = json.loads(decoded)
                    if "result" in msg or "error" in msg:
                        direction = "incoming"
                        # Check for server info
                        server_info = extract_server_info(decoded)
                        if server_info:
                            conn_id = _get_connection_id(dst_ip, dst_port, src_ip, src_port)
                            _server_registry[conn_id] = server_info
                            logger.debug(f"Captured server info for {conn_id}: {server_info}")
                    elif "method" in msg:
                        direction = "outgoing"
                except json.JSONDecodeError:
                    pass

                entry = {
                    "log_id": log_id,
                    "timestamp": ts,
                    "src_ip": src_ip,
                    "src_port": src_port,
                    "dst_ip": dst_ip,
                    "dst_port": dst_port,
                    "direction": direction,
                    "message": decoded,
                    "transport_type": transport,
                }

                # Build metadata
                metadata = {}

                # Add server info if we have it
                conn_id = _get_connection_id(src_ip, src_port, dst_ip, dst_port)
                if conn_id in _server_registry:
                    server_info = _server_registry[conn_id]
                    metadata["server_name"] = server_info["name"]
                    metadata["server_version"] = server_info["version"]

                # MCPHawk's own traffic will be identified by server_name in metadata

                if metadata:
                    entry["metadata"] = json.dumps(metadata)

                log_message(entry)

                # Convert timestamp to ISO only for WebSocket broadcast
                broadcast_entry = dict(entry)
                broadcast_entry["timestamp"] = ts.isoformat()
                _broadcast_in_any_loop(broadcast_entry)
        except Exception as e:
            logger.debug(f"JSON decode failed: {e}")


def start_sniffer(filter_expr: str = "tcp and port 12345", auto_detect: bool = False, debug: bool = False, excluded_ports: list[int] | None = None) -> None:
    """
    Start sniffing packets on the appropriate interface.
    - On macOS: use `lo0`
    - On Linux: default interface

    Args:
        filter_expr: BPF filter expression
        auto_detect: If True, automatically detect MCP traffic on any port
        debug: If True, enable debug logging
        excluded_ports: List of ports to exclude from capture
    """
    global _auto_detect_mode, _excluded_ports
    _auto_detect_mode = auto_detect
    _excluded_ports = set(excluded_ports) if excluded_ports else set()

    # Configure logging based on debug flag
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
        logger.setLevel(logging.DEBUG)

    logger.debug(f"Starting sniffer with filter: {filter_expr}")
    if auto_detect:
        logger.debug("Auto-detect mode enabled")

    # Ensure better pcap support on macOS
    conf.use_pcap = True

    try:
        iface = "lo0" if platform.system() == "Darwin" else None
        sniff(filter=filter_expr, iface=iface, prn=packet_callback, store=False)
    except KeyboardInterrupt:
        logger.debug("Sniffer interrupted by user")
        raise
