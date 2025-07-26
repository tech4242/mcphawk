# Traffic Generation Examples

This directory contains example servers and clients for generating MCP traffic to test MCPHawk.

## TCP-based MCP

### Server
```bash
python3 tcp_server.py
```
Starts a TCP MCP server on port 12345.

### Client
```bash
python3 tcp_client.py
```
Sends various MCP messages to the TCP server.

## WebSocket-based MCP

### Server
```bash
python3 ws_server.py
```
Starts a WebSocket MCP server on port 8765.

### Client
```bash
python3 ws_client.py
```
Sends various MCP messages to the WebSocket server.

## Generate All Traffic

To generate both TCP and WebSocket traffic for testing:

```bash
python3 generate_all.py
```

This will:
1. Start both TCP and WebSocket servers
2. Send a variety of MCP messages to each
3. Display the traffic being generated
4. Clean up when done

## Testing with MCPHawk

In another terminal, run MCPHawk to capture the traffic:

```bash
# Capture TCP traffic
sudo mcphawk sniff --port 12345

# Capture WebSocket traffic
sudo mcphawk sniff --port 8765

# Capture both
sudo mcphawk sniff --filter "tcp port 12345 or tcp port 8765"

# Or use auto-detect
sudo mcphawk sniff --auto-detect
```