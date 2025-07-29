#!/usr/bin/env python3
"""Test MCPHawk server using the official MCP SDK client."""

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_with_sdk_client():
    """Test using the SDK's official client."""

    # Connect to the server
    async with streamablehttp_client("http://localhost:8765/mcp") as (read_stream, write_stream, session_id):
        print(f"Connected with session ID: {session_id}")

        # Create a session
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize
            print("\n1. Initializing...")
            await session.initialize()
            print("Initialized successfully")

            # List tools
            print("\n2. Listing tools...")
            tools_result = await session.list_tools()
            print(f"Available tools: {len(tools_result.tools)}")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call a tool
            print("\n3. Calling get_stats...")
            result = await session.call_tool("get_stats", arguments={})
            print("Result:")
            for content in result.content:
                print(f"  {content.text}")

            # Try query_traffic
            print("\n4. Querying recent traffic...")
            result = await session.call_tool("query_traffic", arguments={"limit": 5})
            print("Result:")
            for content in result.content:
                data = json.loads(content.text)
                print(f"  Found {len(data)} log entries")


if __name__ == "__main__":
    print("Testing MCPHawk MCP Server with SDK Client")
    print("==========================================")
    print("Make sure the server is running with:")
    print("  mcphawk mcp --transport http --mcp-port 8765")
    print()

    try:
        asyncio.run(test_with_sdk_client())
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

