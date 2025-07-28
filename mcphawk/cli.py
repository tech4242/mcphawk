import asyncio
import logging
import sys
import threading

import typer

from mcphawk.logger import init_db
from mcphawk.mcp_server.server import MCPHawkServer
from mcphawk.sniffer import start_sniffer
from mcphawk.web.server import run_web

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
    auto_detect: bool = typer.Option(False, "--auto-detect", "-a", help="Auto-detect MCP traffic on any port"),
    with_mcp: bool = typer.Option(False, "--with-mcp", help="Start MCP server alongside sniffer"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for MCP server (stdio if not specified)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
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

    # Start MCP server if requested
    mcp_thread = None
    if with_mcp:
        print("[MCPHawk] Starting MCP server on stdio (configure in your MCP client)")
        server = MCPHawkServer()

        def run_mcp():
            asyncio.run(server.run_stdio())

        mcp_thread = threading.Thread(target=run_mcp, daemon=True)
        mcp_thread.start()

    print(f"[MCPHawk] Starting sniffer with filter: {filter_expr}")
    if with_mcp and filter_expr != "tcp":
        print(f"[MCPHawk] Note: MCP server traffic on port {mcp_port} will be excluded from capture")
    print("[MCPHawk] Press Ctrl+C to stop...")

    try:
        # Exclude MCP port if running MCP server
        excluded_ports = [mcp_port] if with_mcp else []
        start_sniffer(
            filter_expr=filter_expr,
            auto_detect=auto_detect,
            debug=debug,
            excluded_ports=excluded_ports
        )
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
    web_port: int = typer.Option(8000, "--web-port", help="Web server port"),
    with_mcp: bool = typer.Option(False, "--with-mcp", help="Start MCP server alongside web UI"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for MCP server (stdio if not specified)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
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

    # Start MCP server if requested
    mcp_thread = None
    if with_mcp:
        print("[MCPHawk] Starting MCP server on stdio (configure in your MCP client)")
        server = MCPHawkServer()

        def run_mcp():
            asyncio.run(server.run_stdio())

        mcp_thread = threading.Thread(target=run_mcp, daemon=True)
        mcp_thread.start()

    # Update filter to exclude MCP port if needed
    if with_mcp and filter_expr and filter_expr != "tcp":
        print(f"[MCPHawk] Note: MCP server traffic on port {mcp_port} will be excluded from capture")

    run_web(
        sniffer=not no_sniffer,
        host=host,
        port=web_port,
        filter_expr=filter_expr,
        auto_detect=auto_detect,
        debug=debug,
        excluded_ports=[mcp_port] if with_mcp else []
    )


@app.command()
def mcp(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport type: stdio or tcp"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for TCP transport (ignored for stdio)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Run MCPHawk MCP server standalone (query existing captured data)."""
    print(f"[MCPHawk] Starting MCP server (transport: {transport})")

    if transport == "stdio":
        print("[MCPHawk] Use this server with MCP clients by configuring stdio transport")
        print("[MCPHawk] Example MCP client configuration:")
        print("""
{
  "mcpServers": {
    "mcphawk": {
      "command": "mcphawk",
      "args": ["mcp"]
    }
  }
}
        """)
    elif transport == "tcp":
        print(f"[MCPHawk] MCP server will listen on port {mcp_port}")
        print("[MCPHawk] Note: TCP transport not yet implemented")
        raise typer.Exit(1)
    else:
        print(f"[ERROR] Unknown transport: {transport}")
        raise typer.Exit(1)

    # Create and run MCP server
    server = MCPHawkServer()

    try:
        asyncio.run(server.run_stdio())
    except KeyboardInterrupt:
        print("\n[MCPHawk] MCP server stopped.")
        sys.exit(0)
