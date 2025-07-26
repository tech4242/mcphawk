import asyncio
import logging
import platform
from datetime import datetime, timezone

# Suppress Scapy warnings before importing
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

from scapy.all import IP, TCP, Raw, conf, sniff  # noqa: E402

from mcphawk.logger import log_message  # noqa: E402
from mcphawk.web.broadcaster import broadcast_new_log  # noqa: E402
from mcphawk.ws_reassembly import process_ws_packet  # noqa: E402

# Set up logger for this module
logger = logging.getLogger(__name__)


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

# Track established WebSocket connections
_ws_connections = set()

def packet_callback(pkt):
    """
    Callback for every sniffed packet.
    Extract JSON-RPC messages from raw TCP payloads.
    """
    if pkt.haslayer(Raw):
        raw_payload = pkt[Raw].load
        if not _auto_detect_mode:  # Less verbose in auto-detect mode
            logger.debug(f"Raw payload: {raw_payload[:60]}...")

        # First, try to process as WebSocket traffic
        if pkt.haslayer(TCP) and pkt.haslayer(IP):
            src_ip = pkt[IP].src
            dst_ip = pkt[IP].dst
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport

            # Check if this might be WebSocket traffic
            is_ws_frame = False
            is_http_upgrade = False

            if len(raw_payload) > 0:
                first_byte = raw_payload[0]
                # Check for WebSocket frames (masked or unmasked)
                # Valid first bytes: 0x80-0x8F (FIN=1) or 0x00-0x0F (FIN=0)
                # With common opcodes: 0x1 (text), 0x2 (binary), 0x8 (close), 0x9 (ping), 0xa (pong)
                # Masked client frames: 0x81 -> 0xC1, 0x82 -> 0xC2, etc.
                is_ws_frame = (
                    (0x80 <= first_byte <= 0x8F) or  # Unmasked frames
                    (0x00 <= first_byte <= 0x0F) or  # Fragmented frames
                    (0xC0 <= first_byte <= 0xCF)     # Masked frames (common case)
                )

                # Also check for HTTP upgrade
                is_http_upgrade = (
                    raw_payload[:4] == b'HTTP' or
                    raw_payload[:3] == b'GET' or
                    b'Upgrade: websocket' in raw_payload
                )

            # Check if this is a known WebSocket connection
            conn_key = (src_ip, src_port, dst_ip, dst_port)
            reverse_key = (dst_ip, dst_port, src_ip, src_port)
            is_known_ws = conn_key in _ws_connections or reverse_key in _ws_connections

            if is_ws_frame or is_http_upgrade or is_known_ws:
                logger.debug(f"Detected WebSocket traffic: is_frame={is_ws_frame}, is_http={is_http_upgrade}, is_known={is_known_ws}, first_byte={hex(first_byte) if len(raw_payload) > 0 else 'N/A'}")

                # Mark this as a WebSocket connection
                if is_ws_frame or is_http_upgrade:
                    _ws_connections.add(conn_key)
                    _ws_connections.add(reverse_key)

                # Process WebSocket frames
                messages = process_ws_packet(src_ip, src_port, dst_ip, dst_port, raw_payload)
                logger.debug(f"process_ws_packet returned {len(messages)} messages")

                for msg in messages:
                    logger.debug(f"WebSocket message captured: {msg}")

                    ts = datetime.now(tz=timezone.utc)

                    # In auto-detect mode, log when we find MCP traffic on a new port
                    if _auto_detect_mode and "jsonrpc" in msg:
                        print(f"[MCPHawk] Detected WebSocket MCP traffic on port {src_port} -> {dst_port}")

                    entry = {
                        "timestamp": ts,
                        "src_ip": src_ip,
                        "src_port": src_port,
                        "dst_ip": dst_ip,
                        "dst_port": dst_port,
                        "direction": "unknown",
                        "message": msg,
                    }

                    log_message(entry)

                    # Convert timestamp to ISO only for WebSocket broadcast
                    broadcast_entry = dict(entry)
                    broadcast_entry["timestamp"] = ts.isoformat()
                    _broadcast_in_any_loop(broadcast_entry)

                # If we processed WebSocket frames, return early
                if messages:
                    return

        # Otherwise, try to process as raw JSON-RPC
        try:
            decoded = raw_payload.decode("utf-8", errors="ignore")
            if decoded.startswith("{") and "jsonrpc" in decoded:
                logger.debug(f"Sniffer captured: {decoded}")

                ts = datetime.now(tz=timezone.utc)
                src_port = pkt[TCP].sport if pkt.haslayer(TCP) else 0
                dst_port = pkt[TCP].dport if pkt.haslayer(TCP) else 0

                # In auto-detect mode, log when we find MCP traffic on a new port
                if _auto_detect_mode:
                    print(f"[MCPHawk] Detected MCP traffic on port {src_port} -> {dst_port}")

                entry = {
                    "timestamp": ts,
                    "src_ip": pkt[IP].src if pkt.haslayer(IP) else "",
                    "src_port": src_port,
                    "dst_ip": pkt[IP].dst if pkt.haslayer(IP) else "",
                    "dst_port": dst_port,
                    "direction": "unknown",
                    "message": decoded,
                }

                log_message(entry)

                # Convert timestamp to ISO only for WebSocket broadcast
                broadcast_entry = dict(entry)
                broadcast_entry["timestamp"] = ts.isoformat()
                _broadcast_in_any_loop(broadcast_entry)
        except Exception as e:
            logger.debug(f"JSON decode failed: {e}")


def start_sniffer(filter_expr: str = "tcp and port 12345", auto_detect: bool = False, debug: bool = False) -> None:
    """
    Start sniffing packets on the appropriate interface.
    - On macOS: use `lo0`
    - On Linux: default interface

    Args:
        filter_expr: BPF filter expression
        auto_detect: If True, automatically detect MCP traffic on any port
        debug: If True, enable debug logging
    """
    global _auto_detect_mode
    _auto_detect_mode = auto_detect

    # Configure logging based on debug flag
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
        logger.setLevel(logging.DEBUG)

    logger.debug(f"Starting sniffer with filter: {filter_expr}")
    if auto_detect:
        logger.debug("Auto-detect mode enabled")

    # Ensure better pcap support on macOS
    conf.use_pcap = True

    iface = "lo0" if platform.system() == "Darwin" else None
    sniff(filter=filter_expr, iface=iface, prn=packet_callback, store=False)
