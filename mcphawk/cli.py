"""MCPHawk CLI - MCP traffic analyzer with TUI."""

import logging
import sys

import typer

from mcphawk.logger import init_db
from mcphawk.sniffer import start_sniffer
from mcphawk.wrapper import run_wrapper

# Suppress Scapy warnings about network interfaces
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

# Setup logger for CLI
logger = logging.getLogger("mcphawk.cli")

# Typer multi-command app
app = typer.Typer(help="MCPHawk: MCP traffic analyzer with TUI")

# Initialize database once when CLI starts
init_db()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """MCPHawk: MCP traffic analyzer.

    Run without a subcommand to launch the TUI viewer.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand = launch TUI viewer
        from mcphawk.tui.app import MCPHawkApp

        tui_app = MCPHawkApp()
        tui_app.run()


@app.command()
def sniff(
    port: int = typer.Option(None, "--port", "-p", help="TCP port to monitor"),
    filter: str = typer.Option(
        None, "--filter", "-f", help="Custom BPF filter expression"
    ),
    auto_detect: bool = typer.Option(
        False, "--auto-detect", "-a", help="Auto-detect MCP traffic on any port"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
):
    """Capture HTTP/SSE MCP traffic (headless, logs to DB).

    Run this in the background, then use 'mcphawk' to view traffic in TUI.

    Examples:
        mcphawk sniff --port 3000 &
        mcphawk sniff --auto-detect &
    """
    # Configure logging
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
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
        filter_expr = filter
    elif port:
        filter_expr = f"tcp port {port}"
    elif auto_detect:
        filter_expr = "tcp"
        logger.info("Auto-detect mode: monitoring all TCP traffic for MCP messages")
    else:
        filter_expr = "tcp"

    logger.info(f"Starting sniffer with filter: {filter_expr}")
    logger.info("Capturing traffic to database. Use 'mcphawk' to view in TUI.")
    logger.info("Press Ctrl+C to stop...")

    try:
        start_sniffer(
            filter_expr=filter_expr,
            auto_detect=auto_detect,
            debug=debug,
        )
    except KeyboardInterrupt:
        logger.info("Sniffer stopped.")
        sys.exit(0)


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def wrap(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
):
    """Wrap an MCP server to capture stdio traffic transparently.

    Usage:
        mcphawk wrap /path/to/mcp-server --arg1 --arg2

    Configure in Claude Desktop/Code settings:
        Instead of:
            "command": "/path/to/mcp-server",
            "args": ["--arg1", "--arg2"]

        Use:
            "command": "mcphawk",
            "args": ["wrap", "/path/to/mcp-server", "--arg1", "--arg2"]

    The wrapper logs all traffic to the database. Use 'mcphawk' to view in TUI.
    """
    # Get the command from remaining args
    command = ctx.args
    if not command:
        logger.error("No command specified to wrap")
        raise typer.Exit(1)

    # Configure logging
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)  # Use stderr to avoid interfering with stdio
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    logger.info(f"Starting MCP wrapper for: {' '.join(command)}")

    # Run the wrapper
    exit_code = run_wrapper(command, debug=debug)
    sys.exit(exit_code)


if __name__ == "__main__":
    app()
