import os
import socket
import sqlite3
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from scapy.all import Ether
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

from mcphawk.logger import init_db, set_db_path
from mcphawk.sniffer import packet_callback, start_sniffer

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
    host = "127.0.0.1"

    # Use port 0 to let OS assign an available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_sock:
        temp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        temp_sock.bind((host, 0))
        _, port = temp_sock.getsockname()

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
    import mcphawk
    assert hasattr(mcphawk, "__version__")


class TestAutoDetect:
    """Test auto-detect mode functionality."""

    def setup_method(self):
        """Reset global state before each test."""
        import mcphawk.sniffer
        mcphawk.sniffer._auto_detect_mode = False

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    @patch('builtins.print')
    def test_auto_detect_prints_port_info(self, mock_print, mock_broadcast, mock_log):
        """Test that auto-detect mode prints port information when MCP traffic is found."""
        import mcphawk.sniffer
        mcphawk.sniffer._auto_detect_mode = True

        # Create a mock packet with MCP JSON-RPC
        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=b'{"jsonrpc":"2.0","method":"test","id":1}'),
            IP: MagicMock(src="10.0.0.1", dst="10.0.0.2"),
            TCP: MagicMock(sport=54321, dport=3000)
        }[layer]

        packet_callback(mock_pkt)

        # Check that port detection message was printed
        mock_print.assert_any_call("[MCPHawk] Detected MCP traffic on port 54321 -> 3000")

        # Verify log_message was called
        assert mock_log.called
        logged_entry = mock_log.call_args[0][0]
        assert logged_entry["src_port"] == 54321
        assert logged_entry["dst_port"] == 3000
        assert "test" in logged_entry["message"]

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    @patch('builtins.print')
    def test_non_auto_detect_no_port_print(self, mock_print, mock_broadcast, mock_log):
        """Test that port info is not printed when not in auto-detect mode."""
        import mcphawk.sniffer
        mcphawk.sniffer._auto_detect_mode = False

        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=b'{"jsonrpc":"2.0","method":"test","id":1}'),
            IP: MagicMock(src="10.0.0.1", dst="10.0.0.2"),
            TCP: MagicMock(sport=3000, dport=54321)
        }[layer]

        packet_callback(mock_pkt)

        # Should not print port detection message
        for call_args in mock_print.call_args_list:
            assert "[MCPHawk] Detected MCP traffic on port" not in str(call_args)

    @patch('mcphawk.sniffer.sniff')
    def test_start_sniffer_auto_detect_flag(self, mock_sniff):
        """Test that start_sniffer sets auto_detect mode and uses correct filter."""
        start_sniffer(filter_expr="tcp", auto_detect=True)

        # Check that auto_detect mode was enabled
        import mcphawk.sniffer
        assert mcphawk.sniffer._auto_detect_mode == True

        # Check sniff was called with tcp filter
        mock_sniff.assert_called_once()
        call_kwargs = mock_sniff.call_args[1]
        assert call_kwargs["filter"] == "tcp"
