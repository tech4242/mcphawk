from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import sqlite3
import asyncio
from typing import List
from mcp_shark.logger import DB_FILE  # keep import for global variable ref

app = FastAPI()


# --- Serve Static HTML ---
@app.get("/")
def read_root():
    with open("mcp_shark/web/static/index.html") as f:
        return HTMLResponse(f.read())


# --- REST API for historical logs ---
@app.get("/logs")
def get_logs(limit: int = 50):
    """
    Return the latest MCP logs from the current database.
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS logs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "timestamp TEXT, src_ip TEXT, dst_ip TEXT, "
        "src_port INTEGER, dst_port INTEGER, "
        "direction TEXT, message TEXT)"
    )
    cur.execute(
        "SELECT timestamp, src_ip, dst_ip, message "
        "FROM logs ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "timestamp": r[0],
            "src": r[1],
            "dst": r[2],
            "message": r[3]
        }
        for r in rows
    ]


# --- WebSocket for live updates ---
active_connections: List[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_connections.append(ws)
    try:
        while True:
            await asyncio.sleep(10)  # Keep alive
    except:
        active_connections.remove(ws)


async def broadcast_new_log(log: dict):
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(log)
        except:
            dead.append(ws)
    for ws in dead:
        active_connections.remove(ws)

