#!/bin/bash

# Test MCPHawk MCP Server (SDK version) with SSE response handling

MCP_URL="http://localhost:8765/mcp"

echo "Testing MCPHawk MCP Server (SDK version) with SSE"
echo "================================================="

# 1. Initialize WITHOUT session ID
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

# Extract session ID
SESSION_ID=$(echo "$response" | grep -i "mcp-session-id:" | sed 's/.*: //' | tr -d '\r\n')
echo "Session ID: $SESSION_ID"

# Extract JSON from SSE response
json_data=$(echo "$response" | grep "^data: " | sed 's/^data: //')
echo "Response JSON:"
echo "$json_data" | jq .

sleep 1

# 2. List tools
echo -e "\n2. Listing tools..."
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

# Extract JSON from SSE
json_data=$(echo "$response" | grep "^data: " | sed 's/^data: //')
echo "$json_data" | jq .

sleep 1

# 3. Call a tool
echo -e "\n3. Getting stats..."
response=$(curl -s -i -X POST $MCP_URL \
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

json_data=$(echo "$response" | grep "^data: " | sed 's/^data: //')
echo "$json_data" | jq .

# 4. Test standard MCP notification (not custom)
echo -e "\n4. Sending standard initialized notification..."
curl -s -i -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }' | head -10

echo -e "\n\nNote: Responses use Server-Sent Events (SSE) format"
echo "The sniffer might not capture SSE responses properly"