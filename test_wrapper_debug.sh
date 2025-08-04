#!/bin/bash
# Test the wrapper directly to see if it's working

echo "Testing MCPHawk wrapper..."
echo ""

# Test 1: Check if mcphawk is in PATH
echo "1. Checking mcphawk command:"
which mcphawk
echo ""

# Test 2: Run the wrapper with a simple echo command
echo "2. Testing wrapper with echo command:"
mcphawk wrap echo '{"jsonrpc":"2.0","method":"test","id":1}'
echo ""

# Test 3: Test the wrapper with mcphawk mcp
echo "3. Testing wrapper with mcphawk mcp (send one message then Ctrl+C):"
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | mcphawk wrap mcphawk mcp --debug