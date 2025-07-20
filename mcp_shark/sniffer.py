import logging
import warnings
from datetime import datetime, UTC

from scapy.all import sniff, Raw, TCP, conf

from mcp_shark.logger import init_db, log_message
from mcp_shark.models import MCPMessageLog
from mcp_shark.ws_reassembly import process_ws_packet

# Suppress Scapy noisy logs
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
conf.verb = 0
warnings.filterwarnings("ignore", category=UserWarning)


def packet_callback(packet):
    """
    Callback for each sniffed packet. Handles WebSocket reassembly first,
    falls back to raw TCP if no complete WebSocket messages are found.
    """
    if packet.haslayer(Raw) and packet.haslayer(TCP):
        raw_data = packet[Raw].load
        src_ip = packet[0][1].src
        dst_ip = packet[0][1].dst
        src_port = packet[TCP].sport
        dst_port = packet[TCP].dport

        # --- Try WebSocket reassembly first ---
        messages = process_ws_packet(
            src_ip, src_port, dst_ip, dst_port, raw_data
        )

        if not messages and b"jsonrpc" in raw_data:
            # Fallback: raw TCP JSON-RPC detection
            try:
                messages = [raw_data.decode("utf-8", errors="ignore")]
            except UnicodeDecodeError:
                messages = []

        for msg in messages:
            if "jsonrpc" in msg:
                entry: MCPMessageLog = {
                    "timestamp": datetime.now(UTC),
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "direction": "unknown",
                    "message": msg
                }

                print(
                    f"[MCP-Shark] {src_ip}:{src_port} → "
                    f"{dst_ip}:{dst_port} | {msg[:100]}..."
                )
                log_message(entry)


def start_sniffer(filter: str = "tcp and host 127.0.0.1") -> None:
    """
    Start sniffing network traffic using Scapy with the given BPF filter.
    """
    print(f"[MCP-Shark] Sniffing with filter: {filter}")
    init_db()
    sniff(filter=filter, prn=packet_callback, store=0)
