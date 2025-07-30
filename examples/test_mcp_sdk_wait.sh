#!/bin/bash

# Test MCPHawk MCP Server with proper initialization wait

MCP_URL="http://localhost:8765/mcp"

echo "Testing MCPHawk MCP Server (SDK version)"
echo "========================================"

# 1. Initialize
echo -e "\n1. Initializing MCP session..."
response=$(curl -s -i -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
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
  }')

SESSION_ID=$(echo "$response" | grep -i "mcp-session-id:" | sed 's/.*: //' | tr -d '\r\n')
echo "Session ID: $SESSION_ID"

# 2. Send initialized notification (this might be required by SDK)
echo -e "\n2. Sending initialized notification to complete handshake..."
curl -s -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }'

echo "Waiting for initialization to complete..."
sleep 2

# 3. Now try listing tools
echo -e "\n3. Listing tools..."
response=$(curl -s -i -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
  }')

json_data=$(echo "$response" | grep "^data: " | sed 's/^data: //')
if [ -n "$json_data" ]; then
    echo "$json_data" | jq .
else
    echo "Raw response:"
    echo "$response" | tail -20
fi

# 4. Test calling a tool
echo -e "\n4. Calling get_stats tool..."
response=$(curl -s -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_stats",
      "arguments": {}
    },
    "id": 3
  }')

# Try to extract JSON - SDK might return plain JSON for errors
echo "$response" | jq . 2>/dev/null || echo "$response"