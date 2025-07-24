"""
MCP-Shark CLI (Guaranteed Multi-Command Version)
"""

import logging
import sys
import typer
from mcp_shark.web.server import run_web
from mcp_shark.sniffer import start_sniffer
from mcp_shark.logger import init_db

# Suppress Scapy warnings about network interfaces
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# ✅ Typer multi-command app
app = typer.Typer(help="MCP-Shark: Passive MCP traffic sniffer + dashboard")

# Initialize database once when CLI starts
init_db()


@app.command()
def sniff(
    port: int = typer.Option(None, "--port", "-p", help="TCP port to monitor"),
    filter: str = typer.Option(None, "--filter", "-f", help="Custom BPF filter expression"),
    auto_detect: bool = typer.Option(False, "--auto-detect", "-a", help="Auto-detect MCP traffic on any port")
):
    """Start sniffing MCP traffic (console output only)."""
    # Validate that user specified either port, filter, or auto-detect
    if not any([port, filter, auto_detect]):
        print("[ERROR] You must specify either --port, --filter, or --auto-detect")
        print("Examples:")
        print("  mcp-shark sniff --port 3000")
        print("  mcp-shark sniff --filter 'tcp port 3000 or tcp port 3001'")
        print("  mcp-shark sniff --auto-detect")
        raise typer.Exit(1)
    
    if filter:
        # User provided custom filter
        filter_expr = filter
    elif port:
        # User provided specific port
        filter_expr = f"tcp port {port}"
    else:
        # Auto-detect mode - capture all TCP traffic
        filter_expr = "tcp"
        print("[MCP-Shark] Auto-detect mode: monitoring all TCP traffic for MCP messages")
    
    print(f"[MCP-Shark] Starting sniffer with filter: {filter_expr}")
    print("[MCP-Shark] Press Ctrl+C to stop...")
    try:
        start_sniffer(filter_expr=filter_expr, auto_detect=auto_detect)
    except KeyboardInterrupt:
        print("\n[MCP-Shark] Sniffer stopped.")
        sys.exit(0)


@app.command()
def web(
    port: int = typer.Option(None, "--port", "-p", help="TCP port to monitor for MCP traffic"),
    filter: str = typer.Option(None, "--filter", "-f", help="Custom BPF filter expression"),
    auto_detect: bool = typer.Option(False, "--auto-detect", "-a", help="Auto-detect MCP traffic on any port"),
    no_sniffer: bool = typer.Option(False, "--no-sniffer", help="Disable sniffer (view historical logs only)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Web server host"),
    web_port: int = typer.Option(8000, "--web-port", help="Web server port")
):
    """Start the MCP-Shark dashboard with sniffer."""
    # If sniffer is enabled, validate that user specified either port, filter, or auto-detect
    if not no_sniffer and not any([port, filter, auto_detect]):
        print("[ERROR] You must specify either --port, --filter, or --auto-detect (or use --no-sniffer)")
        print("Examples:")
        print("  mcp-shark web --port 3000")
        print("  mcp-shark web --filter 'tcp port 3000 or tcp port 3001'")
        print("  mcp-shark web --auto-detect")
        print("  mcp-shark web --no-sniffer  # View historical logs only")
        raise typer.Exit(1)
    
    # Prepare filter expression
    if filter:
        filter_expr = filter
    elif port:
        filter_expr = f"tcp port {port}"
    elif auto_detect:
        filter_expr = "tcp"
    else:
        filter_expr = None  # No sniffer
    
    run_web(
        sniffer=not no_sniffer, 
        host=host, 
        port=web_port,
        filter_expr=filter_expr,
        auto_detect=auto_detect
    )
