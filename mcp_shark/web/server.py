"""
MCP-Shark Web Server (Phase 1.7 - Fixed UI Updates)

Provides:
- REST API for log retrieval
- WebSocket endpoint for live traffic updates
- Static serving of the Vue dashboard
"""

import os
import asyncio
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from mcp_shark.logger import fetch_logs
from mcp_shark.web.broadcaster import active_clients

DEBUG = True

app = FastAPI()

# Allow local UI dev or CDN-based dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/logs")
def get_logs(limit: int = 50):
    """
    Retrieve recent logs from the database.

    Args:
        limit: Maximum number of logs to return (default: 50).

    Returns:
        List of log entries as JSON-serializable dictionaries.
    """
    logs = fetch_logs(limit)
    if DEBUG:
        print(f"[DEBUG] /logs returned {len(logs)} entries")
    return JSONResponse(content=[
        {
            **log,
            "timestamp": log["timestamp"].isoformat()  # ensure JSON-friendly
        }
        for log in logs
    ])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live traffic updates.
    Keeps the connection alive until the client disconnects.
    """
    await websocket.accept()
    active_clients.append(websocket)
    if DEBUG:
        print(f"[DEBUG] WebSocket connected: {len(active_clients)} active clients")

    try:
        while True:
            # Keep connection alive with ping
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),  # Wait for any message
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                # Send ping to check if client is still alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except (WebSocketDisconnect, ConnectionResetError, Exception) as e:
        if DEBUG and not isinstance(e, WebSocketDisconnect):
            print(f"[DEBUG] WebSocket error: {type(e).__name__}: {e}")
    finally:
        if websocket in active_clients:
            active_clients.remove(websocket)
        if DEBUG:
            print(f"[DEBUG] WebSocket disconnected: {len(active_clients)} active clients")


def _start_sniffer_thread(filter_expr: str, auto_detect: bool = False):
    """
    Start the sniffer in a dedicated daemon thread.
    
    Args:
        filter_expr: BPF filter expression for the sniffer.
        auto_detect: Whether to auto-detect MCP traffic.
    """
    from mcp_shark.sniffer import start_sniffer

    def safe_start():
        if DEBUG:
            print(f"[DEBUG] Sniffer thread starting with filter: {filter_expr}, auto_detect: {auto_detect}")
        return start_sniffer(filter_expr=filter_expr, auto_detect=auto_detect)

    thread = threading.Thread(target=safe_start, daemon=True)
    thread.start()


def run_web(sniffer: bool = True, host: str = "127.0.0.1", port: int = 8000, filter_expr: str = None, auto_detect: bool = False):
    """
    Run the web server and optionally the sniffer.

    Args:
        sniffer: Whether to start the sniffer in a background thread.
        host: Host to bind the server to.
        port: Port to run the server on.
        filter_expr: BPF filter expression for the sniffer.
        auto_detect: Whether to auto-detect MCP traffic.
    """
    if sniffer:
        if not filter_expr:
            raise ValueError("filter_expr is required when sniffer is enabled")
        _start_sniffer_thread(filter_expr, auto_detect)

    if sniffer:
        print(f"[MCP-Shark] Starting sniffer and dashboard on http://{host}:{port}")
        print(f"[MCP-Shark] Using filter: {filter_expr}")
        if auto_detect:
            print("[MCP-Shark] Auto-detect mode enabled")
    else:
        print(f"[MCP-Shark] Starting dashboard only (no sniffer) on http://{host}:{port}")

    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Serve static Vue dashboard (production mode)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
