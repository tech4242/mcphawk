import logging
import sys
import typer
from mcphawk.web.server import run_web
from mcphawk.sniffer import start_sniffer
from mcphawk.logger import init_db

# Suppress Scapy warnings about network interfaces
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# ✅ Typer multi-command app
app = typer.Typer(help="MCPHawk: Passive MCP traffic sniffer + dashboard")

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
        print("  mcphawk sniff --port 3000")
        print("  mcphawk sniff --filter 'tcp port 3000 or tcp port 3001'")
        print("  mcphawk sniff --auto-detect")
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
        print("[MCPHawk] Auto-detect mode: monitoring all TCP traffic for MCP messages")
    
    print(f"[MCPHawk] Starting sniffer with filter: {filter_expr}")
    print("[MCPHawk] Press Ctrl+C to stop...")
    try:
        start_sniffer(filter_expr=filter_expr, auto_detect=auto_detect)
    except KeyboardInterrupt:
        print("\n[MCPHawk] Sniffer stopped.")
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
    """Start the MCPHawk dashboard with sniffer."""
    # If sniffer is enabled, validate that user specified either port, filter, or auto-detect
    if not no_sniffer and not any([port, filter, auto_detect]):
        print("[ERROR] You must specify either --port, --filter, or --auto-detect (or use --no-sniffer)")
        print("Examples:")
        print("  mcphawk web --port 3000")
        print("  mcphawk web --filter 'tcp port 3000 or tcp port 3001'")
        print("  mcphawk web --auto-detect")
        print("  mcphawk web --no-sniffer  # View historical logs only")
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
