"""Generate realistic MCP traffic through `mcphawk wrap`, then open the UI.

    python examples/demo/run_demo.py
    mcphawk up --open

Runs three servers (one modern 2026-07-28, two with the legacy handshake) from
a single client process, so they show up as one run with a shared timeline.
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

SERVERS = Path(__file__).with_name("servers.py")


def wrapped(name: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcphawk", "wrap", "--name", name, "--", sys.executable, str(SERVERS), name],
        env=dict(os.environ),  # the SDK passes a filtered env by default; keep MCPHAWK_DB
    )


async def agent_turns() -> None:
    async with (
        Client(wrapped("weather")) as weather,
        Client(wrapped("docs"), mode="legacy") as docs,
        Client(wrapped("flaky"), mode="legacy") as tickets,
    ):
        for client in (weather, docs, tickets):
            await client.list_tools()
        await docs.call_tool("search_docs", {"query": "deploy rollback", "limit": 5})
        await weather.call_tool("get_weather", {"city": "Berlin"})
        await weather.call_tool("forecast", {"city": "Berlin", "days": 5})
        await weather.call_tool("get_weather", {"city": "Atlantis"})
        await docs.call_tool("read_page", {"page_id": "runbook-42"})
        for _ in range(3):  # an agent stuck in a loop
            await docs.call_tool("search_docs", {"query": "rollback", "limit": 3})
        await tickets.call_tool("create_ticket", {"title": "Rollback failed", "priority": "urgent"})
        await tickets.call_tool("create_ticket", {"title": "Rollback failed"})
        await tickets.call_tool("slow_report", {})


if __name__ == "__main__":
    asyncio.run(agent_turns())
    print("Done. Run `mcphawk up --open` to explore the traffic.")
