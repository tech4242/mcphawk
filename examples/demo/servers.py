"""Three small MCP servers for the MCPHawk demo: python servers.py <weather|docs|flaky>."""

import asyncio
import random
import sys

from mcp.server.mcpserver import MCPServer

weather = MCPServer("weather", version="1.4.0", instructions="Current weather and forecasts.")


@weather.tool()
def get_weather(city: str) -> str:
    """Current weather for a city."""
    if city.lower() == "atlantis":
        raise ValueError("unknown city")
    return f"{city}: {random.choice(['sunny', 'light rain', 'overcast'])}, {random.randint(8, 27)}°C"


@weather.tool()
def forecast(city: str, days: int = 3) -> str:
    """Daily forecast for the next few days."""
    return "\n".join(f"Day {d + 1}: {random.randint(8, 27)}°C" for d in range(days))


docs = MCPServer("docs-search", version="0.9.2", instructions=(
    "Search the internal documentation. Always prefer search_docs over reading whole pages. "
    "Results are ranked by relevance and include section anchors. " * 6))

_VERBOSE = (
    "Searches every document in the knowledge base, including archived pages, design notes, "
    "meeting transcripts and API references. Supports boolean operators, phrase queries, "
    "field filters (author:, team:, updated:), fuzzy matching and synonym expansion. " * 8)


@docs.tool(description=_VERBOSE)
def search_docs(query: str, limit: int = 10, include_archived: bool = False,
                team: str | None = None, updated_after: str | None = None) -> str:
    return "\n\n".join(
        f"## Result {i + 1}: {query} in practice\n" + ("Lorem ipsum dolor sit amet. " * 60)
        for i in range(limit))


@docs.tool()
def read_page(page_id: str) -> str:
    """Read one documentation page in full."""
    return f"# Page {page_id}\n" + ("A very long page body. " * 3000)


@docs.tool()
def list_spaces() -> list[str]:
    """List documentation spaces."""
    return ["engineering", "product", "support"]


@docs.tool()
def export_pdf(page_id: str) -> str:
    """Export a page as PDF (rarely useful for agents)."""
    return "ok"


flaky = MCPServer("tickets", version="2.0.0")


@flaky.tool()
async def create_ticket(title: str, priority: str = "normal") -> str:
    """Create a support ticket."""
    await asyncio.sleep(random.uniform(0.05, 0.4))
    if priority == "urgent":
        raise RuntimeError("upstream ticketing API timed out")
    return f"Created TCK-{random.randint(1000, 9999)}: {title}"


@flaky.tool()
async def slow_report() -> str:
    """Generate a weekly report (slow)."""
    await asyncio.sleep(1.5)
    return "Report ready."


if __name__ == "__main__":
    {"weather": weather, "docs": docs, "flaky": flaky}[sys.argv[1]].run("stdio")
