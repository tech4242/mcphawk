"""Tiny line-delimited JSON-RPC server used by the stdio shim tests."""

import json
import sys

print("booting (stray stdout line)", flush=True)
print("stderr noise", file=sys.stderr, flush=True)
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg.get("method") == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {},
                  "serverInfo": {"name": "echo", "version": "0.1"}}
    elif msg.get("method") == "exit":
        sys.exit(3)
    else:
        result = {"echo": msg.get("params")}
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
