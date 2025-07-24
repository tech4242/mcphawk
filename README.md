# mcp-shark 🦈

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
- **Auto-detect mode** - automatically discovers MCP traffic on any port without prior configuration
- **Flexible traffic filtering**:
  - Monitor specific ports with `--port`
  - Use custom BPF filters with `--filter`
  - Auto-detect MCP traffic on all ports with `--auto-detect`
- **Chronological message display** - messages shown in order as captured
- **Message filtering** - view all, requests only, responses only, or notifications only
- **Optional ID-based pairing visualization** - see which requests and responses belong together
- **Real-time statistics** - message counts by type
- **Console-only mode** - use `mcp-shark sniff` for terminal output without web UI
- **Historical log viewing** - use `mcp-shark web --no-sniffer` to view past captures without active sniffing

## mcpinspector vs. mcp-shark

If you want to observe all MCP traffic between any processes, mcp-shark offers unique value as a passive sniffer that mcpinspector does not. If you want to actively test servers, mcpinspector is better. For many workflows, they are complementary tools.

| Feature                                      | mcp-shark | mcpinspector |
|-----------------------------------------------|:---------:|:------------:|
| Passive sniffing (no proxy needed)            |     ✅     |      ❌       |
| Auto-detect MCP traffic on any port           |     ✅     |      ❌       |
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

# Monitor MCP traffic on a specific port (console output)
mcp-shark sniff --port 3000

# Monitor multiple ports with a custom filter
mcp-shark sniff --filter "tcp port 3000 or tcp port 8080"

# Auto-detect MCP traffic on any port
mcp-shark sniff --auto-detect

# Start web UI with sniffer on specific port
mcp-shark web --port 3000

# Start web UI with auto-detect mode
mcp-shark web --auto-detect

# Start web UI with custom filter for multiple ports
mcp-shark web --filter "tcp port 3000 or tcp port 8080"

# View historical logs only (no active sniffing)
mcp-shark web --no-sniffer

# Custom web server configuration
mcp-shark web --port 3000 --host 0.0.0.0 --web-port 9000

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

## Potential Upcoming Features

Vote for features by opening a GitHub issue!

- [x] **Auto-detect MCP traffic** - Automatically discover MCP traffic on any port without prior configuration
- [ ] **Protocol Version Detection** - Identify and display MCP protocol version from captured traffic
- [ ] **Smart Search & Filtering** - Search by method name, params, or any JSON field with regex support
- [ ] **Performance Analytics** - Request/response timing, method frequency charts, and latency distribution
- [ ] **Export & Share** - Export sessions as JSON/CSV, generate shareable links, create HAR-like files
- [ ] **Test Generation** - Auto-generate test cases from captured traffic
- [ ] **Error Analysis** - Highlight errors, group similar issues, show error trends
- [ ] **Session Management** - Save/load capture sessions, compare sessions side-by-side
- [ ] **Interactive Replay** - Click any request to re-send it, edit and replay captured messages
- [ ] **Real-time Alerts** - Alert on specific methods or error patterns with webhook support
- [ ] **Visualization** - Sequence diagrams, resource heat maps, method dependency graphs