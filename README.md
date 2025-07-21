# mcp-shark 🦈

mcp-shark is a passive sniffer for **Model Context Protocol (MCP)** traffic, similar to Wireshark but MCP-focused.

It captures JSON-RPC traffic between MCP clients and WebSocket/TCP-based MCP servers. MCP-Shark can reconstruct full JSON-RPC messages from raw TCP traffic without requiring a handshake.

## What it is
Passive network sniffer for MCP/JSON-RPC traffic (like Wireshark, but protocol-focused).
Captures traffic “on the wire” between any MCP client and server—does not require client/server modification.
Records real traffic (from any tool, agent, or LLM) as it actually flows over TCP/WebSocket.
Web dashboard for live and historical log viewing.
CLI for running as a standalone process.
No proxying or protocol injection—just observes real traffic.

## mcpinspector vs. mcp-shark

If you want to observe all MCP traffic between any processes, mcp-shark offers unique value as a passive sniffer that mcpinspector does not. If you want to actively test servers, mcpinspector is better. For many workflows, they are complementary tools.

| Feature                                    | mcp-shark | mcpinspector |
|---------------------------------------------|:---------:|:------------:|
| Passive sniffing (no proxy needed)          |     ✅     |      ❌       |
| Web UI for live/historical traffic          |     ✅     |      ✅       |
| Can log any traffic (not just via proxy/UI) |     ✅     |      ❌       |
| Manual request crafting/protocol fuzzing    |     ❌     |      ✅       |
| Proxy/bridge between client/server          |     ❌     |      ✅       |
| No client/server config changes required    |     ✅     |      ❌       |

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

# Basic sniffing
mcp-shark

# With a custom filter
mcp-shark --filter "tcp port 12345"

# With a web UI
mcp-shark web

# Get help
mcp-shark --help

# Run dummy mcp server for tests
python3 -m dummy_mcp_server.py

# Run dummy MCP call
(echo -n '{"jsonrpc":"2.0","method":"ping"}'; sleep 1) | nc 127.0.0.1 12345
```