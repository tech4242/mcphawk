<div align="center">
  <img src="examples/branding/mcphawk_logo.png" alt="MCPHawk Logo" height="130">
  
  [![CI](https://github.com/tech4242/mcphawk/actions/workflows/ci.yml/badge.svg)](https://github.com/tech4242/mcphawk/actions/workflows/ci.yml)
  [![codecov](https://codecov.io/gh/tech4242/mcphawk/branch/main/graph/badge.svg)](https://codecov.io/gh/tech4242/mcphawk)
  [![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![Vue.js](https://img.shields.io/badge/vue.js-3.x-brightgreen.svg)](https://vuejs.org/)
  [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
  [![PEP8](https://img.shields.io/badge/code%20style-pep8-orange.svg)](https://www.python.org/dev/peps/pep-0008/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

MCPHawk is a passive sniffer for **Model Context Protocol (MCP)** traffic, similar to Wireshark but MCP-focused. It's Wireshark x mcpinspector.

- It captures JSON-RPC traffic between MCP clients and WebSocket/TCP-based MCP servers (IPv4 and IPv6) e.g. from any tool, agent, or LLM
- MCPHawk can reconstruct full JSON-RPC messages from raw TCP traffic without requiring a handshake. 
- It captures traffic "on the wire" between any MCP client and server—does not require client/server modification.

<img src="examples/branding/mcphawk_screenshot.png" alt="MCPHawk Logo" width="100%">

## Features

Non-exhaustive list:
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
- **Console-only mode** - use `mcphawk sniff` for terminal output without web UI
- **Historical log viewing** - use `mcphawk web --no-sniffer` to view past captures without active sniffing
- **Chill UX** 
  - dark mode 🌝
  - expand mode to directly see JSON withtout detailed view
  - filtering 
  - always see if WS connection is up for live updates

## Comparison with Similar Tools

| Feature                                      | MCPHawk | mcpinspector | Wireshark |
|-----------------------------------------------|:---------:|:------------:|:---------:|
| Passive sniffing (no proxy needed)            |     ✅     |      ❌       |     ✅     |
| MCP/JSON-RPC protocol awareness               |     ✅     |      ✅       |     ❌     |
| Auto-detect MCP traffic on any port           |     ✅     |      ❌       |     ❌     |
| Web UI for live/historical traffic            |     ✅     |      ✅       |     ❌     |
| Can capture any traffic (not just via proxy)  |     ✅     |      ❌       |     ✅     |
| JSON-RPC message type detection               |     ✅     |      ❌       |     ❌     |
| Message filtering by type                     |     ✅     |      ❌       |     ❌     |
| Console-only mode (no web UI needed)          |     ✅     |      ❌       |     ✅     |
| Manual request crafting/testing               |     ❌     |      ✅       |     ❌     |
| Interactive tool/prompt testing               |     ❌     |      ✅       |     ❌     |
| Proxy/bridge between client/server            |     ❌     |      ✅       |     ❌     |
| No client/server config changes required      |     ✅     |      ❌       |     ✅     |
| General protocol analysis                     |     ❌     |      ❌       |     ✅     |
| MCP-specific features                         |     ✅     |      ✅       |     ❌     |

**When to use each tool:**
- **MCPHawk**: Best for passively monitoring MCP traffic, debugging live connections, understanding protocol flow
- **mcpinspector**: Best for actively testing MCP servers, crafting custom requests, interactive debugging
- **Wireshark**: Best for general network analysis, non-MCP protocols, deep packet inspection

## TLS/HTTPS Limitations

MCPHawk captures **unencrypted** MCP traffic only. It cannot decrypt:
- HTTPS/WSS (WebSocket Secure) connections
- TLS-encrypted TCP connections
- Any SSL/TLS encrypted traffic

**This tool is ideal for:**
- 🛠️ **Local MCP development** - Debug your MCP server implementations
- 🔍 **Understanding MCP protocol** - See actual JSON-RPC message flow
- 🐛 **Troubleshooting local tools** - Monitor Claude Desktop, Cline, etc. with YOUR local MCP servers
- 📊 **Development/staging environments** - Where TLS is often disabled

**Not suitable for:**
- Production traffic analysis (usually encrypted)
- Cloud MCP services (HTTPS/WSS)
- Third-party MCP servers with TLS 

## Installation

### For Users

```bash
# Install from PyPI
pip install mcphawk

# Or install directly from GitHub
pip install git+https://github.com/tech4242/mcphawk.git
```

### Requirements

- **macOS/Linux**: Requires `sudo` for packet capture (standard for network sniffers)
- **Python**: 3.9 or higher
- **Permissions**: Must run with elevated privileges to access network interfaces

### Quick Start

```bash
# Get help
mcphawk --help

# Get help for specific command
mcphawk sniff --help
mcphawk web --help

# Start web UI with auto-detect mode (requires sudo on macOS)
sudo mcphawk web --auto-detect

# Monitor MCP traffic on a specific port (console output)
sudo mcphawk sniff --port 3000

# Monitor multiple ports with a custom filter
sudo mcphawk sniff --filter "tcp port 3000 or tcp port 8080"

# Auto-detect MCP traffic on any port
sudo mcphawk sniff --auto-detect

# Start web UI with sniffer on specific port
sudo mcphawk web --port 3000

# Start web UI with custom filter for multiple ports
sudo mcphawk web --filter "tcp port 3000 or tcp port 8080"

# View historical logs only (no active sniffing)
sudo mcphawk web --no-sniffer

# Custom web server configuration
sudo mcphawk web --port 3000 --host 0.0.0.0 --web-port 9000

# Enable debug output for troubleshooting
sudo mcphawk sniff --port 3000 --debug
sudo mcphawk web --port 3000 --debug
```

## Platform Support

### Tested Platforms
- ✅ **macOS** (Apple Silicon & Intel) - Fully tested
- ✅ **Linux** (Ubuntu, Debian) - Fully tested  
- ⚠️  **Windows** - Experimental (Scapy should work but untested)

### Known Limitations

- Requires elevated privileges (`sudo`) on macOS/Linux for packet capture
- Limited to localhost/loopback interface monitoring
- WebSocket capture requires traffic to be uncompressed
- IPv6 support requires explicit interface configuration on some systems
- High traffic volumes (>1000 msgs/sec) may impact performance

### Troubleshooting

**Permission Denied Error:**
```bash
# On macOS/Linux, use sudo:
sudo mcphawk web --auto-detect
```

**No Traffic Captured:**
- Ensure the MCP server/client is using localhost (127.0.0.1 or ::1)
- Check if traffic is on the expected port
- Try auto-detect mode to find MCP traffic: `--auto-detect`
- On macOS, ensure you're allowing the terminal to capture packets in System Preferences

**WebSocket Traffic Not Showing:**
- Verify the WebSocket connection is uncompressed
- Check if the server is using IPv6 (::1) - MCPHawk supports both IPv4 and IPv6
- Ensure the WebSocket frames contain valid JSON-RPC messages

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
- [ ] **MCP Server Interface** - Expose captured traffic via MCP server for AI agents to query and analyze traffic patterns

... and a few more off the deep end:
- [ ] **TLS/HTTPS Support (MITM Proxy Mode)** - Optional man-in-the-middle proxy with certificate installation for encrypted traffic
- [ ] **External Decryption Integration** - Import decrypted streams from Wireshark, Chrome DevTools, or SSLKEYLOGFILE

## For Developers

```bash
# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
pip3 install -r requirements-dev.txt
pip3 install -e .

# Install frontend dependencies and build
cd frontend
npm install
npm run build
cd ..

# Run tests
python3 -m pytest -v
```

### Some Vue options:

```bash
# Option 1: Use make (recommended)
make dev  # Runs both frontend and backend

# Option 2: Run separately
# Terminal 1 - Frontend with hot reload
cd frontend && npm run dev

# Terminal 2 - Backend
mcphawk web --port 3000

# Option 3: Watch mode
cd frontend && npm run build:watch  # Auto-rebuild on changes
mcphawk web --port 3000           # In another terminal
```

### Testing with Dummy Server

```bash
# Generate various MCP patterns
python3 examples/generate_traffic/generate_all.py
```
