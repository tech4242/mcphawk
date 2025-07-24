"""
MCP-Shark CLI (Guaranteed Multi-Command Version)
"""

import logging
import sys
import typer
from mcp_shark.web.server import run_web
from mcp_shark.sniffer import start_sniffer

# Suppress Scapy warnings about network interfaces
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# ✅ Typer multi-command app
app = typer.Typer(help="MCP-Shark: Passive MCP traffic sniffer + dashboard")


@app.command()
def sniff(
    filter: str = typer.Option("tcp and port 12345", "--filter", "-f", help="BPF filter expression")
):
    """Start sniffing MCP traffic (console output only)."""
    print(f"[MCP-Shark] Starting sniffer with filter: {filter}")
    print("[MCP-Shark] Press Ctrl+C to stop...")
    try:
        start_sniffer(filter_expr=filter)
    except KeyboardInterrupt:
        print("\n[MCP-Shark] Sniffer stopped.")
        sys.exit(0)


@app.command()
def web(
    sniffer: bool = True,
    host: str = "127.0.0.1",
    port: int = 8000
):
    """Start the MCP-Shark dashboard (and sniffer by default)."""
    run_web(sniffer=sniffer, host=host, port=port)
