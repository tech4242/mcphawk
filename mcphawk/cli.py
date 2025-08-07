import asyncio
import logging
import sys
import threading

import typer

from mcphawk.logger import init_db
from mcphawk.mcp_server.server import MCPHawkServer
from mcphawk.sniffer import start_sniffer
from mcphawk.web.server import run_web
from mcphawk.wrapper import run_wrapper

# Suppress Scapy warnings about network interfaces
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# Setup logger for CLI
logger = logging.getLogger("mcphawk.cli")

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
    mcp_transport: str = typer.Option("http", "--mcp-transport", help="MCP transport type: stdio or http"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for MCP HTTP server (ignored for stdio)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Start sniffing MCP traffic (console output only)."""
    # Configure logging - clear existing handlers first
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Validate that user specified either port, filter, or auto-detect
    if not any([port, filter, auto_detect]):
        logger.error("You must specify either --port, --filter, or --auto-detect")
        logger.error("Examples:")
        logger.error("  mcphawk sniff --port 3000")
        logger.error("  mcphawk sniff --filter 'tcp port 3000 or tcp port 3001'")
        logger.error("  mcphawk sniff --auto-detect")
        raise typer.Exit(1)

    # Determine filter expression
    if filter:
        # User provided custom filter
        filter_expr = filter
    elif port:
        # User provided specific port
        filter_expr = f"tcp port {port}"
    elif auto_detect:
        # Auto-detect mode - capture all TCP traffic
        filter_expr = "tcp"
        logger.info("Auto-detect mode: monitoring all TCP traffic for MCP messages")
    else:
        # Default to tcp
        filter_expr = "tcp"

    # Start MCP server if requested
    mcp_thread = None
    excluded_ports = []
    if with_mcp:
        server = MCPHawkServer()

        if mcp_transport == "http":
            logger.info(f"Starting MCP HTTP server on http://localhost:{mcp_port}/mcp")
            # MCPHawk's own MCP traffic will be captured and identified by server name
            def run_mcp():
                asyncio.run(server.run_http(port=mcp_port))
        else:
            logger.info("Starting MCP server on stdio (configure in your MCP client)")
            if debug:
                logger.info("Note: stdio MCP traffic cannot be captured (use HTTP transport for debugging)")
            def run_mcp():
                asyncio.run(server.run_stdio())

        mcp_thread = threading.Thread(target=run_mcp, daemon=True)
        mcp_thread.start()

    logger.info(f"Starting sniffer with filter: {filter_expr}")
    logger.info("Press Ctrl+C to stop...")

    try:
        start_sniffer(
            filter_expr=filter_expr,
            auto_detect=auto_detect,
            debug=debug,
            excluded_ports=excluded_ports
        )
    except KeyboardInterrupt:
        logger.info("Sniffer stopped.")
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
    mcp_transport: str = typer.Option("http", "--mcp-transport", help="MCP transport type: stdio or http"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for MCP HTTP server (ignored for stdio)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Start the MCPHawk dashboard with sniffer."""
    # Configure logging - clear existing handlers first
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # If sniffer is enabled, validate that user specified either port, filter, or auto-detect
    if not no_sniffer and not any([port, filter, auto_detect]):
        logger.error("You must specify either --port, --filter, or --auto-detect (or use --no-sniffer)")
        logger.error("Examples:")
        logger.error("  mcphawk web --port 3000")
        logger.error("  mcphawk web --filter 'tcp port 3000 or tcp port 3001'")
        logger.error("  mcphawk web --auto-detect")
        logger.error("  mcphawk web --no-sniffer  # View historical logs only")
        raise typer.Exit(1)

    # Prepare filter expression
    if no_sniffer:
        filter_expr = None  # No sniffer
    elif filter:
        filter_expr = filter
    elif port:
        filter_expr = f"tcp port {port}"
    elif auto_detect:
        filter_expr = "tcp"
    else:
        filter_expr = "tcp"  # Default

    # Start MCP server if requested
    mcp_thread = None
    excluded_ports = []
    if with_mcp:
        server = MCPHawkServer()

        if mcp_transport == "http":
            logger.info(f"Starting MCP HTTP server on http://localhost:{mcp_port}/mcp")
            # MCPHawk's own MCP traffic will be captured and identified by server name
            def run_mcp():
                asyncio.run(server.run_http(port=mcp_port))
        else:
            logger.info("Starting MCP server on stdio (configure in your MCP client)")
            if debug:
                logger.info("Note: stdio MCP traffic cannot be captured (use HTTP transport for debugging)")
            def run_mcp():
                asyncio.run(server.run_stdio())

        mcp_thread = threading.Thread(target=run_mcp, daemon=True)
        mcp_thread.start()

    run_web(
        sniffer=not no_sniffer,
        host=host,
        port=web_port,
        filter_expr=filter_expr,
        auto_detect=auto_detect,
        debug=debug,
        excluded_ports=excluded_ports,
        with_mcp=with_mcp
    )


@app.command()
def mcp(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport type: stdio or tcp"),
    mcp_port: int = typer.Option(8765, "--mcp-port", help="Port for TCP transport (ignored for stdio)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Run MCPHawk MCP server standalone (query existing captured data)."""
    # Configure logging based on transport and debug flag - clear existing handlers first
    logger.handlers.clear()
    if transport == "stdio":
        # For stdio, all logs must go to stderr to avoid interfering with JSON-RPC on stdout
        handler = logging.StreamHandler(sys.stderr)
    else:
        # For other transports, use stdout
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    logger.info(f"Starting MCP server (transport: {transport})")

    if transport == "stdio":
        logger.debug("Use this server with MCP clients by configuring stdio transport")
        logger.debug("Example MCP client configuration:")
        logger.debug("""
{
  "mcpServers": {
    "mcphawk": {
      "command": "mcphawk",
      "args": ["mcp"]
    }
  }
}
        """)
    elif transport == "http":
        logger.info(f"MCP server will listen on http://localhost:{mcp_port}/mcp")
        logger.debug("Example test command:")
        logger.debug(f"curl -X POST http://localhost:{mcp_port}/mcp -H 'Content-Type: application/json' -d '{{\"jsonrpc\":\"2.0\",\"method\":\"initialize\",\"params\":{{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{{}},\"clientInfo\":{{\"name\":\"test\",\"version\":\"1.0\"}}}},\"id\":1}}'")
    else:
        logger.error(f"Unknown transport: {transport}")
        raise typer.Exit(1)

    # Create and run MCP server
    server = MCPHawkServer()

    try:
        if transport == "stdio":
            asyncio.run(server.run_stdio())
        elif transport == "http":
            asyncio.run(server.run_http(port=mcp_port))
    except KeyboardInterrupt:
        logger.info("MCP server stopped.")
        sys.exit(0)


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def wrap(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Wrap an MCP server to capture stdio traffic transparently.

    Usage:
        mcphawk wrap /path/to/mcp-server --arg1 --arg2

    Configure in Claude Desktop settings:
        Instead of:
            "command": "/path/to/mcp-server",
            "args": ["--arg1", "--arg2"]

        Use:
            "command": "mcphawk",
            "args": ["wrap", "/path/to/mcp-server", "--arg1", "--arg2"]
    """
    # Get the command from remaining args
    command = ctx.args
    if not command:
        logger.error("No command specified to wrap")
        raise typer.Exit(1)

    # Configure logging
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)  # Use stderr to avoid interfering with stdio
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    logger.info(f"Starting MCP wrapper for: {' '.join(command)}")

    # Run the wrapper
    exit_code = run_wrapper(command, debug=debug)
    sys.exit(exit_code)


if __name__ == "__main__":
    app()
