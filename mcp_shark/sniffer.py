"""
Sniffer for MCP-Shark: captures packets and logs JSON-RPC messages.
Cross-platform: works on macOS (loopback) and Linux.
"""

import asyncio
from datetime import UTC, datetime
import json
import logging
import platform

# Suppress Scapy warnings before importing
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

from scapy.all import sniff, IP, TCP, Raw, conf
from mcp_shark.logger import log_message
from mcp_shark.web.broadcaster import broadcast_new_log

DEBUG = True


async def _safe_broadcast(log_entry: dict) -> None:
    try:
        await broadcast_new_log(log_entry)
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Broadcast failed: {e}")


def _broadcast_in_any_loop(log_entry: dict) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_safe_broadcast(log_entry))
    except RuntimeError:
        asyncio.run(_safe_broadcast(log_entry))


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
                if DEBUG:
                    print(f"[DEBUG] Sniffer captured: {decoded}")

                ts = datetime.now(tz=UTC)
                entry = {
                    "timestamp": ts,
                    "src_ip": pkt[IP].src if pkt.haslayer(IP) else "",
                    "src_port": pkt[TCP].sport if pkt.haslayer(TCP) else 0,
                    "dst_ip": pkt[IP].dst if pkt.haslayer(IP) else "",
                    "dst_port": pkt[TCP].dport if pkt.haslayer(TCP) else 0,
                    "direction": "unknown",
                    "message": decoded,
                }

                log_message(entry)

                # Convert timestamp to ISO only for WebSocket broadcast
                broadcast_entry = dict(entry)
                broadcast_entry["timestamp"] = ts.isoformat()
                _broadcast_in_any_loop(broadcast_entry)
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] JSON decode failed: {e}")


def start_sniffer(filter_expr: str = "tcp and port 12345") -> None:
    """
    Start sniffing packets on the appropriate interface.
    - On macOS: use `lo0`
    - On Linux: default interface
    """
    if DEBUG:
        print(f"[DEBUG] Starting sniffer with filter: {filter_expr}")

    # Ensure better pcap support on macOS
    conf.use_pcap = True

    iface = "lo0" if platform.system() == "Darwin" else None
    sniff(filter=filter_expr, iface=iface, prn=packet_callback, store=False)
