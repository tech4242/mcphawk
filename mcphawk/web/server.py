import asyncio
import logging
import os
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from mcphawk.logger import fetch_logs
from mcphawk.web.broadcaster import active_clients
from mcphawk.web.metrics import (
    get_error_timeline,
    get_message_type_distribution,
    get_method_frequency,
    get_performance_metrics,
    get_timeseries_metrics,
    get_transport_distribution,
)

# Set up logger for this module
logger = logging.getLogger(__name__)

# Global flag to track if web server was started with MCP
_with_mcp = False

app = FastAPI()

# Allow local UI dev or CDN-based dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
def get_status():
    """
    Get server status including MCP server status.
    """
    return JSONResponse(content={
        "with_mcp": _with_mcp
    })


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
    logger.debug(f"/logs returned {len(logs)} entries")
    return JSONResponse(content=[
        {
            **log,
            "timestamp": log["timestamp"].isoformat(),  # ensure JSON-friendly
            "transport_type": log.get("transport_type", "unknown")  # ensure transport_type is included
        }
        for log in logs
    ])


@app.get("/api/metrics/timeseries")
def get_timeseries(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
    interval_minutes: int = Query(5, ge=1, le=60),  # noqa: B008
    transport_type: Optional[str] = Query(None),  # noqa: B008
    server_name: Optional[str] = Query(None),  # noqa: B008
):
    """Get time series metrics for message traffic."""
    return get_timeseries_metrics(
        start_time=start_time,
        end_time=end_time,
        interval_minutes=interval_minutes,
        transport_type=transport_type,
        server_name=server_name,
    )


@app.get("/api/metrics/methods")
def get_methods(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),  # noqa: B008
    transport_type: Optional[str] = Query(None),  # noqa: B008
    server_name: Optional[str] = Query(None),  # noqa: B008
):
    """Get frequency of JSON-RPC methods."""
    return get_method_frequency(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        transport_type=transport_type,
        server_name=server_name,
    )


@app.get("/api/metrics/transport")
def get_transport(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
):
    """Get distribution of messages by transport type."""
    return get_transport_distribution(
        start_time=start_time,
        end_time=end_time,
    )


@app.get("/api/metrics/message-types")
def get_message_types(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
    transport_type: Optional[str] = Query(None),  # noqa: B008
):
    """Get distribution of messages by type."""
    return get_message_type_distribution(
        start_time=start_time,
        end_time=end_time,
        transport_type=transport_type,
    )


@app.get("/api/metrics/performance")
def get_performance(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
    transport_type: Optional[str] = Query(None),  # noqa: B008
):
    """Get performance metrics including response times."""
    return get_performance_metrics(
        start_time=start_time,
        end_time=end_time,
        transport_type=transport_type,
    )


@app.get("/api/metrics/errors")
def get_errors(
    start_time: Optional[datetime] = Query(None),  # noqa: B008
    end_time: Optional[datetime] = Query(None),  # noqa: B008
    interval_minutes: int = Query(5, ge=1, le=60),  # noqa: B008
):
    """Get timeline of errors."""
    return get_error_timeline(
        start_time=start_time,
        end_time=end_time,
        interval_minutes=interval_minutes,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live traffic updates.
    Keeps the connection alive until the client disconnects.
    """
    await websocket.accept()
    active_clients.append(websocket)
    logger.debug(f"WebSocket connected: {len(active_clients)} active clients")

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
        if not isinstance(e, WebSocketDisconnect):
            logger.debug(f"WebSocket error: {type(e).__name__}: {e}")
    finally:
        if websocket in active_clients:
            active_clients.remove(websocket)
        logger.debug(f"WebSocket disconnected: {len(active_clients)} active clients")


def _start_sniffer_thread(filter_expr: str, auto_detect: bool = False, debug: bool = False, excluded_ports: Optional[list[int]] = None):
    """
    Start the sniffer in a dedicated daemon thread.

    Args:
        filter_expr: BPF filter expression for the sniffer.
        auto_detect: Whether to auto-detect MCP traffic.
        debug: Whether to enable debug logging.
        excluded_ports: List of ports to exclude from capture.
    """
    from mcphawk.sniffer import start_sniffer

    def safe_start():
        logger.debug(f"Sniffer thread starting with filter: {filter_expr}, auto_detect: {auto_detect}")
        return start_sniffer(filter_expr=filter_expr, auto_detect=auto_detect, debug=debug, excluded_ports=excluded_ports)

    thread = threading.Thread(target=safe_start, daemon=True)
    thread.start()


def run_web(sniffer: bool = True, host: str = "127.0.0.1", port: int = 8000, filter_expr: Optional[str] = None, auto_detect: bool = False, debug: bool = False, excluded_ports: Optional[list[int]] = None, with_mcp: bool = False):
    """
    Run the web server and optionally the sniffer.

    Args:
        sniffer: Whether to start the sniffer in a background thread.
        host: Host to bind the server to.
        port: Port to run the server on.
        filter_expr: BPF filter expression for the sniffer.
        auto_detect: Whether to auto-detect MCP traffic.
        debug: Whether to enable debug logging.
    """
    # Set global MCP flag
    global _with_mcp
    _with_mcp = with_mcp

    # Configure logging based on debug flag first
    if debug:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
        logger.setLevel(logging.DEBUG)
        log_level = "debug"
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger.setLevel(logging.INFO)
        log_level = "warning"  # Only show warnings and errors for uvicorn

    if sniffer:
        if not filter_expr:
            raise ValueError("filter_expr is required when sniffer is enabled")
        _start_sniffer_thread(filter_expr, auto_detect, debug, excluded_ports)

    if sniffer:
        logger.info(f"Starting sniffer and dashboard on http://{host}:{port}")
        logger.info(f"Using filter: {filter_expr}")
        if auto_detect:
            logger.info("Auto-detect mode enabled")
    else:
        logger.info(f"Starting dashboard only (no sniffer) on http://{host}:{port}")

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level=log_level)


# Serve static Vue dashboard (production mode)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Mount static files first for assets
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    # Add specific route for analytics to serve index.html
    @app.get("/analytics")
    async def serve_analytics():
        """Serve index.html for the /analytics route."""
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return JSONResponse(content={"detail": "Not Found"}, status_code=404)
    
    # Mount root static files with html=True for other routes
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
