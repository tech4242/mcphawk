"""
MCP-Shark CLI (Final Working Version)
"""

import typer
from mcp_shark.web.server import run_web

# ✅ Multi-command Typer app
app = typer.Typer(help="MCP-Shark: Passive MCP traffic sniffer + dashboard")


@app.command()
def web(
    sniffer: bool = True,
    host: str = "127.0.0.1",
    port: int = 8000
):
    """Start the MCP-Shark dashboard (and sniffer by default)."""
    run_web(sniffer=sniffer, host=host, port=port)
