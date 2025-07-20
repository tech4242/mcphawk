import threading
import socket
import time
import sqlite3
import os
import pytest
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw
from scapy.all import Ether
from mcp_shark.sniffer import packet_callback
from mcp_shark.logger import init_db, set_db_path

# --- TEST DB PATH ---
TEST_DB_DIR = "tests/test_logs"
TEST_DB = os.path.join(TEST_DB_DIR, "test_mcp_sniffer_logs.db")


@pytest.fixture(scope="module", autouse=True)
def clean_db():
    """Prepare a clean SQLite DB for tests."""
    os.makedirs(TEST_DB_DIR, exist_ok=True)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    set_db_path(TEST_DB)
    init_db()
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
    time.sleep(0.5)
    yield host, port


def test_packet_callback(dummy_server):
    """Simulate sending an MCP-like JSON-RPC packet and verify it's logged."""
    host, port = dummy_server

    jsonrpc_msg = (
        b'{"jsonrpc":"2.0","method":"callTool","params":{"tool":"weather",'
        b'"location":"Berlin"}}'
    )
    pkt = (
        Ether()
        / IP(src="127.0.0.1", dst=host)
        / TCP(sport=55555, dport=port)
        / Raw(load=jsonrpc_msg)
    )
    packet_callback(pkt)

    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()
    cur.execute("SELECT message FROM logs ORDER BY id DESC LIMIT 1;")
    logged_msg = cur.fetchone()[0]
    conn.close()

    assert "weather" in logged_msg
    assert "Berlin" in logged_msg


def test_import():
    import mcp_shark
    assert hasattr(mcp_shark, "__version__")
