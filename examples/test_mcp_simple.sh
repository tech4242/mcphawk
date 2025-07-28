#!/bin/bash

# Simple test for MCPHawk MCP Server
# Run MCPHawk with: sudo mcphawk web --auto-detect --with-mcp --mcp-transport http --mcp-port 8765 --debug

SESSION_ID="test-$(date +%s)"
echo "Testing with session: $SESSION_ID"

# Single test request
echo "Sending initialize request..."
curl -X POST http://localhost:8765/mcp \
  -H 'Content-Type: application/json' \
  -H "X-Session-Id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0"
      }
    },
    "id": 1
  }'

echo -e "\n\nCheck http://localhost:8000 for captured traffic"