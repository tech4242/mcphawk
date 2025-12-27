<div align="center">
  <img src="examples/branding/mcphawk_logo.png" alt="MCPHawk Logo" height="130">

  [![CI](https://github.com/tech4242/mcphawk/actions/workflows/ci.yml/badge.svg)](https://github.com/tech4242/mcphawk/actions/workflows/ci.yml)
  [![codecov](https://codecov.io/gh/tech4242/mcphawk/branch/main/graph/badge.svg)](https://codecov.io/gh/tech4242/mcphawk)
  [![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
  [![Typer](https://img.shields.io/badge/CLI-Typer-informational?style=flat&logo=python&color=2bbc8a)](https://typer.tiangolo.com/)
  [![Textual](https://img.shields.io/badge/TUI-Textual-blueviolet.svg)](https://textual.textualize.io/)
  [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
  [![PEP8](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://www.python.org/dev/peps/pep-0008/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

MCPHawk is a developer-focused traffic analyzer for **Model Context Protocol (MCP)**, providing deep visibility into MCP client-server interactions through a terminal-based UI. Think of it as Wireshark meets mcpinspector, purpose-built for local MCP development.

**Key Capabilities:**
- **Protocol-Aware Capture**: Understands MCP's JSON-RPC 2.0 transport layer, capturing and reassembling messages from stdio pipes and HTTP streams
- **Transport Agnostic**: Monitors MCP traffic across all standard transports (stdio, Streamable HTTP, HTTP+SSE)
- **Full Message Reconstruction**: Advanced stream reassembly handles fragmented packets, chunked HTTP transfers, and SSE streams
- **Terminal UI**: Real-time log viewer with filtering, search, and message details - no browser needed

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  mcphawk sniff  │────▶│                 │
│  (network)      │     │    SQLite DB    │
└─────────────────┘     │                 │
                        │  mcphawk_logs   │◀────┐
┌─────────────────┐     │       .db       │     │
│  mcphawk wrap   │────▶│                 │     │
│  (stdio)        │     └────────┬────────┘     │
└─────────────────┘              │              │
                                 │ poll         │
                                 ▼              │
                        ┌─────────────────┐     │
                        │    mcphawk      │─────┘
                        │    (TUI)        │
                        └─────────────────┘
```

**Workflow:**
1. Run capture commands (`sniff` or `wrap`) in the background or configure in MCP client
2. Launch `mcphawk` to view all captured traffic in real-time TUI
3. Multiple capture sources can feed into one viewer

## Core Features

### MCP Protocol Analysis
- **Complete JSON-RPC 2.0 Support**: Correctly identifies and categorizes all MCP message types
  - **Requests**: Method calls with unique IDs for correlation
  - **Responses**: Success results and error responses with matching IDs
  - **Notifications**: Fire-and-forget method calls without IDs
- **Transport Detection**: Auto-detects transport type from traffic patterns
- **Protocol Compliance**: Validates JSON-RPC 2.0 structure

### Advanced Capture Capabilities
- **Auto-Discovery Mode**: Intelligently detects MCP traffic on any port using pattern matching
- **TCP Stream Reassembly**: Reconstructs complete messages from fragmented packets
- **Multi-Stream Tracking**: Simultaneously monitors multiple MCP client-server connections
- **IPv4/IPv6 Dual Stack**: Native support for both IP protocols

### Terminal UI
- **Real-Time Log Table**: Live traffic updates with color-coded message types
- **Filtering**: Filter by message type, transport, or server
- **Search**: Find specific messages by content
- **Message Details**: Expandable view with full JSON and metadata

### MCP Transport Support

| Official MCP Transport | Protocol Version | Capture Support | Details |
|------------------------|------------------|:---------------:|---------|
| **stdio** | All versions | ✅ Full | Process wrapper transparently captures stdin/stdout between client and server |
| **Streamable HTTP** | 2025-03-26+ | ✅ Full | HTTP POST with optional SSE streaming responses |
| **HTTP+SSE** | 2024-11-05 | ✅ Full | Legacy transport with separate SSE endpoint |

> **Note:** HTTP+SSE is deprecated as of MCP spec 2025-03-26 but still detected for legacy support. Raw TCP traffic with JSON-RPC is also captured and marked as "unknown" transport type.

## Installation

### From PyPI

```bash
pip install mcphawk
```

### From GitHub

```bash
pip install git+https://github.com/tech4242/mcphawk.git
```

### Requirements

- **macOS/Linux**: Requires `sudo` for network packet capture
- **Python**: 3.10 or higher
- **Permissions**: Elevated privileges needed to access network interfaces

## Quick Start

```bash
# Launch TUI viewer (reads from database)
mcphawk

# Capture HTTP/SSE traffic on specific port (requires sudo)
sudo mcphawk sniff --port 3000

# Auto-detect MCP traffic on any port
sudo mcphawk sniff --auto-detect

# Capture with custom BPF filter
sudo mcphawk sniff --filter "tcp port 3000 or tcp port 8080"

# Wrap an MCP server to capture stdio traffic
mcphawk wrap /path/to/mcp-server --arg1 --arg2

# Example: Wrap Context7 MCP server
mcphawk wrap npx -y @upstash/context7-mcp@latest
```

### Claude Desktop Integration

Configure Claude Desktop to use the wrapper for stdio capture:

```json
{
  "mcpServers": {
    "context7": {
      "command": "mcphawk",
      "args": ["wrap", "npx", "-y", "@upstash/context7-mcp@latest"]
    }
  }
}
```

## CLI Commands

| Command | Role | Mode |
|---------|------|------|
| `mcphawk` | TUI viewer | Foreground, interactive |
| `mcphawk sniff --port XXXX` | HTTP/SSE network capture | Headless, logs to DB |
| `mcphawk wrap /path/to/server` | stdio capture | Headless, logs to DB |

### TUI Keybindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `f` | Toggle filter panel |
| `/` | Focus search |
| `r` | Refresh |
| `c` | Clear entries |
| `a` | Toggle auto-scroll |
| `Enter` | View message details |
| `Escape` | Close detail view |

## Comparison with Similar Tools

| Feature | MCPHawk | mcpinspector | Wireshark |
|---------|:-------:|:------------:|:---------:|
| Passive sniffing (no proxy needed) | ✅ | ❌ | ✅ |
| MCP/JSON-RPC protocol awareness | ✅ | ✅ | ❌ |
| SSE/Chunked HTTP support | ✅ | ❓ | ❌ |
| TCP stream reassembly | ✅ | ❌ | ✅ |
| Auto-detect MCP traffic | ✅ | ❌ | ❌ |
| Terminal UI | ✅ | ❌ | ❌ |
| JSON-RPC message type detection | ✅ | ❌ | ❌ |
| No client/server config needed | ✅ | ❌ | ✅ |
| Proxy/MITM capabilities | ✅ (stdio) | ✅ | ❌ |

**When to use each tool:**
- **MCPHawk**: Passive monitoring, protocol analysis, debugging MCP implementations
- **mcpinspector**: Active testing, crafting requests, interactive debugging with proxy
- **Wireshark**: General network analysis, non-MCP protocols, packet-level inspection

## TLS/HTTPS Limitations

MCPHawk captures **unencrypted** MCP traffic only. It cannot decrypt:
- HTTPS/WSS (WebSocket Secure) connections
- TLS-encrypted TCP connections

**This tool is ideal for:**
- Local MCP development and debugging
- Understanding MCP protocol message flow
- Troubleshooting local tools (Claude Desktop, Cline, etc.)
- Development/staging environments where TLS is disabled

## Platform Support

### Tested Platforms
- ✅ **macOS** (Apple Silicon & Intel) - Fully tested
- ✅ **Linux** (Ubuntu, Debian) - Fully tested
- ⚠️ **Windows** - Experimental (Scapy should work but untested)

### Troubleshooting

**Permission Denied Error:**
```bash
# On macOS/Linux, use sudo for network capture:
sudo mcphawk sniff --auto-detect
```

**No Traffic Captured:**
- Ensure the MCP server/client is using localhost (127.0.0.1 or ::1)
- Check if traffic is on the expected port
- Try auto-detect mode: `--auto-detect`
- Verify traffic is unencrypted (not HTTPS/TLS)

**SSE/HTTP Responses Not Showing:**
- Confirm the server uses standard SSE format
- Enable debug mode: `--debug`

## For Developers

```bash
# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements-dev.txt
pip3 install -e .

# Run tests
make test

# Run linter
make lint

# Run with coverage
make coverage
```

## Potential Upcoming Features

Vote for features by opening a GitHub issue!

- [x] Auto-detect MCP traffic
- [x] Stdio capture via process wrapper
- [x] Terminal UI with real-time updates
- [ ] Protocol Version Detection
- [ ] Performance Analytics (timing, latency)
- [ ] Export & Share (JSON/CSV export)
- [ ] Session Management (save/load sessions)
- [ ] Real-time Alerts (webhook support)

## License

MIT License - see [LICENSE](LICENSE) for details.
