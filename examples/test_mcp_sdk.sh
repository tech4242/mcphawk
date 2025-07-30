#!/bin/bash

# Test MCPHawk MCP Server (SDK version) with proper session flow
# The SDK requires: 
# 1. First initialize request WITHOUT session ID
# 2. Server returns session ID in response
# 3. Use that session ID for subsequent requests

MCP_URL="http://localhost:8765/mcp"

echo "Testing MCPHawk MCP Server (SDK version)"
echo "========================================"

# 1. Initialize WITHOUT session ID - server will assign one
echo -e "\n1. Initializing MCP session (no session ID)..."
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

echo "$response"

# Extract session ID from response headers
SESSION_ID=$(echo "$response" | grep -i "mcp-session-id:" | sed 's/.*: //' | tr -d '\r\n')

if [ -z "$SESSION_ID" ]; then
    echo "ERROR: No session ID received from server"
    exit 1
fi

echo -e "\nReceived session ID: $SESSION_ID"

sleep 1

# 2. Now use the server-provided session ID for subsequent requests
echo -e "\n2. Listing tools with session ID..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
  }' | jq .

sleep 1

# 3. Test a notification (should return no response)
echo -e "\n3. Sending notification..."
curl -i -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/progress",
    "params": {
      "progress": 50,
      "message": "Test progress notification"
    }
  }'

echo -e "\n\nCheck http://localhost:8000 for captured traffic"