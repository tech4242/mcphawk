# mcp-shark 🦈

mcp-shark is a passive sniffer for **Model Context Protocol (MCP)** traffic, similar to Wireshark but MCP-focused.

It captures JSON-RPC traffic between MCP clients and WebSocket/TCP-based MCP servers. MCP-Shark can reconstruct full JSON-RPC messages from raw TCP traffic without requiring a handshake.

## What it is
Passive network sniffer for MCP/JSON-RPC traffic (like Wireshark, but protocol-focused).
Captures traffic "on the wire" between any MCP client and server—does not require client/server modification.
Records real traffic (from any tool, agent, or LLM) as it actually flows over TCP/WebSocket.
Web dashboard for live and historical log viewing with proper JSON-RPC message type detection.
CLI for running as a standalone process or with web UI.
No proxying or protocol injection—just observes real traffic.

## Features

- **Proper JSON-RPC 2.0 message type detection**:
  - Requests (method + id)
  - Responses (result/error + id)
  - Notifications (method without id)
  - Error responses
- **Chronological message display** - messages shown in order as captured
- **Message filtering** - view all, requests only, responses only, or notifications only
- **Optional ID-based pairing visualization** - see which requests and responses belong together
- **Real-time statistics** - message counts by type
- **Console-only mode** - use `mcp-shark sniff` for terminal output without web UI

## mcpinspector vs. mcp-shark

If you want to observe all MCP traffic between any processes, mcp-shark offers unique value as a passive sniffer that mcpinspector does not. If you want to actively test servers, mcpinspector is better. For many workflows, they are complementary tools.

| Feature                                      | mcp-shark | mcpinspector |
|-----------------------------------------------|:---------:|:------------:|
| Passive sniffing (no proxy needed)            |     ✅     |      ❌       |
| Web UI for live/historical traffic            |     ✅     |      ✅       |
| Can capture any traffic (not just via proxy)  |     ✅     |      ❌       |
| JSON-RPC message type detection               |     ✅     |      ❌       |
| Message filtering by type                     |     ✅     |      ❌       |
| Console-only mode (no web UI needed)          |     ✅     |      ❌       |
| Manual request crafting/testing               |     ❌     |      ✅       |
| Interactive tool/prompt testing               |     ❌     |      ✅       |
| Proxy/bridge between client/server            |     ❌     |      ✅       |
| No client/server config changes required      |     ✅     |      ❌       |

## Running locally

Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate

pip3 install -r requirements-dev.txt
pip3 install -e .

python3 -m pytest -v
```

## Installing

```bash
pip install mcp-shark

# Basic sniffing (console output only)
mcp-shark sniff

# Sniff with a custom filter
mcp-shark sniff --filter "tcp port 8080"

# Start web UI with sniffer
mcp-shark web

# Start web UI without sniffer (view historical logs only)
mcp-shark web --no-sniffer

# Start web UI on custom host/port
mcp-shark web --host 0.0.0.0 --port 9000

# Get help
mcp-shark --help

# Get help for specific command
mcp-shark sniff --help
mcp-shark web --help

# Run dummy mcp server for tests
python3 dummy_mcp_server.py

# Run dummy MCP call
(echo -n '{"jsonrpc":"2.0","method":"ping"}'; sleep 1) | nc 127.0.0.1 12345

# Test various MCP patterns (after starting dummy server)
python3 test_mcp_patterns.py
```