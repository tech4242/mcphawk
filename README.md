# mcp-shark 🦈

**MCP-Shark** is a passive sniffer for **Model Context Protocol (MCP)** traffic, similar to Wireshark but MCP-focused.  
It captures JSON-RPC traffic between MCP clients and WebSocket/TCP-based MCP servers.

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

# Get help
mcp-shark --help
```