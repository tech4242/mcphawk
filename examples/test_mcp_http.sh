#!/bin/bash

# Test MCPHawk MCP Server with various requests
# Make sure MCPHawk is running with:
# sudo mcphawk web --auto-detect --with-mcp --mcp-transport http --mcp-port 8765 --debug

SESSION_ID="test-session-$(date +%s)"
MCP_URL="http://localhost:8765/mcp"

echo "Testing MCPHawk MCP Server with session: $SESSION_ID"
echo "================================================"

# 1. Initialize session
echo -e "\n1. Initializing MCP session..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
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
  }' | jq .

sleep 1

# 2. Send initialized notification
echo -e "\n2. Sending initialized notification..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }' | jq .

sleep 1

# 3. List available tools
echo -e "\n3. Listing available tools..."
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

# 4. Get traffic statistics
echo -e "\n4. Getting traffic statistics..."
curl -X POST $MCP_URL \
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
  }' | jq .

sleep 1

# 5. Query recent traffic
echo -e "\n5. Querying recent traffic (limit 10)..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_traffic",
      "arguments": {
        "limit": 10
      }
    },
    "id": 4
  }' | jq .

sleep 1

# 6. List unique methods captured
echo -e "\n6. Listing unique JSON-RPC methods..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "list_methods",
      "arguments": {}
    },
    "id": 5
  }' | jq .

sleep 1

# 7. Search for specific traffic
echo -e "\n7. Searching for 'initialize' in traffic..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_traffic",
      "arguments": {
        "search_term": "initialize"
      }
    },
    "id": 6
  }' | jq .

sleep 1

# 8. Test error handling - call non-existent tool
echo -e "\n8. Testing error handling (calling non-existent tool)..."
curl -X POST $MCP_URL \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "non_existent_tool",
      "arguments": {}
    },
    "id": 7
  }' | jq .

sleep 1

# 9. Send a notification (no ID, no response expected)
echo -e "\n9. Sending a notification..."
curl -X POST $MCP_URL \
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

echo -e "\n\nAll tests completed!"
echo "Check the MCPHawk web UI at http://localhost:8000 to see:"
echo "- All requests marked with purple 'MCP' badges"
echo "- Use the MCPHawk toggle button to filter these messages"
echo "- Click on messages to see full JSON details"