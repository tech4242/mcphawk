"""A real MCP server built with the official SDK (stdio or Streamable HTTP)."""

import sys

from mcp.server.mcpserver import MCPServer

server = MCPServer("sdk-weather", version="3.1.4", instructions="Weather lookups.")


@server.tool()
def get_weather(city: str) -> str:
    """Current weather for a city."""
    return f"Sunny in {city}"


@server.tool()
def explode() -> str:
    """Always fails."""
    raise ValueError("kaboom")


if __name__ == "__main__":
    server.run("stdio" if len(sys.argv) < 2 else sys.argv[1])
