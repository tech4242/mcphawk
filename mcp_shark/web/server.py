"""
MCP-Shark Web Server (Phase 1.6 - Final)

Provides:
- REST API for log retrieval
- WebSocket endpoint for live traffic updates
- Static serving of the Vue dashboard
"""

import os
import asyncio
import threading
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mcp_shark.logger import fetch_logs
from mcp_shark.web.broadcaster import active_clients

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
        List of log entries as dictionaries.
    """
    return fetch_logs(limit)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live traffic updates.
    Keeps the connection alive until the client disconnects.
    """
    await websocket.accept()
    active_clients.append(websocket)

    try:
        while True:
            await asyncio.sleep(30)
    except Exception:
        pass
    finally:
        if websocket in active_clients:
            active_clients.remove(websocket)


def _start_sniffer_thread():
    """
    Start the sniffer in a dedicated daemon thread.
    """
    from mcp_shark.sniffer import start_sniffer

    def safe_start():
        return start_sniffer()  # ✅ force call with no arguments

    thread = threading.Thread(target=safe_start, daemon=True)
    thread.start()


def run_web(sniffer: bool = True, host: str = "127.0.0.1", port: int = 8000):
    """
    Run the web server and optionally the sniffer.

    Args:
        sniffer: Whether to start the sniffer in a background thread.
        host: Host to bind the server to.
        port: Port to run the server on.
    """
    if sniffer:
        _start_sniffer_thread()

    print(f"[MCP-Shark] Starting sniffer and dashboard on http://{host}:{port}")

    import uvicorn
    uvicorn.run(app, host=host, port=port)


# Serve static Vue dashboard (production mode)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
