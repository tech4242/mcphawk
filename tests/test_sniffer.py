import threading
import socket
import time
import sqlite3
import pytest
from mcp_shark.sniffer import packet_callback
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw
from scapy.all import Ether
from mcp_shark.logger import init_db

DB_FILE = "mcp_sniffer_logs.db"


@pytest.fixture(scope="module", autouse=True)
def clean_db():
    """Reset the SQLite DB before tests."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute("DELETE FROM logs;")
    conn.close()
    yield


@pytest.fixture(scope="module")
def dummy_server():
    """Spin up a dummy MCP-like TCP echo server in a background thread."""
    host, port = "127.0.0.1", 12345

    def server():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen()
            conn, _ = s.accept()
            with conn:
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    conn.sendall(data)

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    time.sleep(0.5)  # Give server time to start
    yield host, port


def test_packet_callback(dummy_server):
    """Simulate sending an MCP-like JSON-RPC packet and verify it's logged."""
    host, port = dummy_server

    # --- Create a fake MCP JSON-RPC Scapy packet ---
    jsonrpc_msg = (
        b'{"jsonrpc":"2.0","method":"callTool","params":'
        b'{"tool":"weather","location":"Berlin"}}'
    )
    pkt = (
        Ether()
        / IP(src="127.0.0.1", dst=host)
        / TCP(sport=55555, dport=port)
        / Raw(load=jsonrpc_msg)
    )
    # --- Trigger MCP-Shark's callback ---
    packet_callback(pkt)

    # --- Verify the message was logged in SQLite ---
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT message FROM logs ORDER BY id DESC LIMIT 1;")
    logged_msg = cur.fetchone()[0]
    conn.close()

    assert "weather" in logged_msg
    assert "Berlin" in logged_msg


def test_import():
    import mcp_shark
    assert hasattr(mcp_shark, "__version__")
    assert mcp_shark.__version__ == "0.1.0"
