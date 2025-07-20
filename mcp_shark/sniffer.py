"""
Sniffer for MCP-Shark: captures packets and logs JSON-RPC messages.
"""

import asyncio
import json
from scapy.all import sniff, IP, TCP, Raw
from mcp_shark.logger import log_message
from mcp_shark.web.broadcaster import broadcast_new_log

DEBUG = True


async def _safe_broadcast(message: str) -> None:
    """Safely broadcast to all connected WebSocket clients."""
    try:
        await broadcast_new_log(message)
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Broadcast failed: {e}")


def _broadcast_in_any_loop(message: str) -> None:
    """Handle broadcasting depending on whether an event loop exists."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_safe_broadcast(message))
    except RuntimeError:
        asyncio.run(_safe_broadcast(message))


def packet_callback(pkt):
    """
    Callback for every sniffed packet.
    Extract JSON-RPC messages from raw TCP payloads.
    """
    if pkt.haslayer(Raw):
        raw_payload = pkt[Raw].load
        if DEBUG:
            print(f"[DEBUG] Raw payload: {raw_payload[:60]}...")

        try:
            decoded = raw_payload.decode("utf-8", errors="ignore")
            if decoded.startswith("{") and "jsonrpc" in decoded:
                msg = json.loads(decoded)
                if DEBUG:
                    print(f"[DEBUG] Sniffer captured: {msg}")

                entry = {
                    "src_ip": pkt[IP].src if pkt.haslayer(IP) else "",
                    "src_port": pkt[TCP].sport if pkt.haslayer(TCP) else 0,
                    "dst_ip": pkt[IP].dst if pkt.haslayer(IP) else "",
                    "dst_port": pkt[TCP].dport if pkt.haslayer(TCP) else 0,
                    "message": decoded,
                }
                log_message(entry)
                _broadcast_in_any_loop(decoded)
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] JSON decode failed: {e}")


def start_sniffer(filter_expr: str = "tcp and host 127.0.0.1") -> None:
    """Start sniffing packets."""
    if DEBUG:
        print(f"[DEBUG] Starting sniffer with filter: {filter_expr}")
    sniff(filter=filter_expr, prn=packet_callback, store=False)
