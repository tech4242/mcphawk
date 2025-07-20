from scapy.all import sniff, Raw, TCP
from datetime import datetime, UTC
from .logger import init_db, log_message
from .models import MCPMessageLog


def packet_callback(packet):
    if packet.haslayer(Raw) and packet.haslayer(TCP):
        raw_data = packet[Raw].load
        if b"jsonrpc" in raw_data:  # MCP traffic heuristic
            try:
                decoded = raw_data.decode("utf-8", errors="ignore")
                src_ip = packet[0][1].src
                dst_ip = packet[0][1].dst
                src_port = packet[TCP].sport
                dst_port = packet[TCP].dport

                entry: MCPMessageLog = {
                    "timestamp": datetime.now(tz=UTC),
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "src_port": src_port,
                    "dst_port": dst_port,
                    "direction": "unknown",  # Will improve later
                    "message": decoded
                }

                print(f"[MCP-Shark] {src_ip}:{src_port} → {dst_ip}:{dst_port} | {decoded[:100]}...")
                log_message(entry)

            except Exception:
                pass


def start_sniffer(filter: str = "tcp and host 127.0.0.1") -> None:
    init_db()
    sniff(filter=filter, prn=packet_callback, store=0)
