import os
import socket
import sqlite3
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from scapy.all import Ether
from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.packet import Raw

from mcphawk.logger import init_db, set_db_path
from mcphawk.sniffer import packet_callback, start_sniffer

# --- TEST DB PATH ---
TEST_DB_DIR = "tests/test_logs"
TEST_DB = os.path.join(TEST_DB_DIR, "test_mcp_sniffer_logs.db")


@pytest.fixture(scope="module")
def clean_db():
    """Prepare a clean SQLite DB for tests."""
    # Save original DB path
    import mcphawk.logger as logger_module
    original_path = logger_module.DB_PATH

    os.makedirs(TEST_DB_DIR, exist_ok=True)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    set_db_path(TEST_DB)
    init_db()
    yield

    # Restore original DB path
    logger_module.DB_PATH = original_path


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


def test_packet_callback(clean_db, dummy_server):
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
    cur.execute("SELECT message FROM logs ORDER BY log_id DESC LIMIT 1;")
    logged_msg = cur.fetchone()[0]
    conn.close()

    assert "weather" in logged_msg
    assert "Berlin" in logged_msg



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


class TestHTTPParsing:
    """Test HTTP request/response parsing for MCP over HTTP."""

    def setup_method(self):
        """Reset global state before each test."""
        import mcphawk.sniffer
        # Clear MCPHawk MCP ports
        mcphawk.sniffer._mcphawk_mcp_ports.clear()

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    def test_http_post_request_parsing(self, mock_broadcast, mock_log):
        """Test parsing of HTTP POST request with JSON-RPC body."""
        http_request = (
            b'POST /mcp HTTP/1.1\r\n'
            b'Host: localhost:8765\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 89\r\n'
            b'\r\n'
            b'{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05"},"id":1}'
        )

        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=http_request),
            IP: MagicMock(src="127.0.0.1", dst="127.0.0.1"),
            TCP: MagicMock(sport=54321, dport=8765)
        }[layer]

        packet_callback(mock_pkt)

        # Verify the JSON-RPC body was extracted and logged
        assert mock_log.called
        logged_entry = mock_log.call_args[0][0]
        assert logged_entry["message"] == '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05"},"id":1}'
        assert logged_entry["traffic_type"] == "TCP/Direct"
        assert logged_entry["src_port"] == 54321
        assert logged_entry["dst_port"] == 8765

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    def test_http_response_parsing(self, mock_broadcast, mock_log):
        """Test parsing of HTTP response with JSON-RPC body."""
        http_response = (
            b'HTTP/1.1 200 OK\r\n'
            b'Content-Type: application/json\r\n'
            b'Content-Length: 50\r\n'
            b'\r\n'
            b'{"jsonrpc":"2.0","result":{"status":"ok"},"id":1}'
        )

        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=http_response),
            IP: MagicMock(src="127.0.0.1", dst="127.0.0.1"),
            TCP: MagicMock(sport=8765, dport=54321)
        }[layer]

        packet_callback(mock_pkt)

        # Verify the JSON-RPC body was extracted and logged
        assert mock_log.called
        logged_entry = mock_log.call_args[0][0]
        assert logged_entry["message"] == '{"jsonrpc":"2.0","result":{"status":"ok"},"id":1}'
        assert logged_entry["traffic_type"] == "TCP/Direct"
        assert logged_entry["src_port"] == 8765
        assert logged_entry["dst_port"] == 54321

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    def test_http_without_jsonrpc_ignored(self, mock_broadcast, mock_log):
        """Test that HTTP requests without JSON-RPC content are ignored."""
        http_request = (
            b'POST /api/test HTTP/1.1\r\n'
            b'Host: localhost:8765\r\n'
            b'Content-Type: application/json\r\n'
            b'\r\n'
            b'{"data":"not json-rpc"}'
        )

        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=http_request),
            IP: MagicMock(src="127.0.0.1", dst="127.0.0.1"),
            TCP: MagicMock(sport=54321, dport=8765)
        }[layer]

        packet_callback(mock_pkt)

        # Should not log non-JSON-RPC content
        assert not mock_log.called


    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    def test_mcphawk_mcp_traffic_metadata(self, mock_broadcast, mock_log):
        """Test that MCPHawk's own MCP traffic is tagged with metadata."""
        import mcphawk.sniffer
        # Set up MCPHawk MCP ports for this test
        mcphawk.sniffer._mcphawk_mcp_ports = {8765}

        http_request = (
            b'POST /mcp HTTP/1.1\r\n'
            b'Host: localhost:8765\r\n'
            b'Content-Type: application/json\r\n'
            b'\r\n'
            b'{"jsonrpc":"2.0","method":"test","id":1}'
        )

        mock_pkt = MagicMock()
        # Note: haslayer should return True for IP but False for IPv6
        mock_pkt.haslayer.side_effect = lambda layer: {
            Raw: True,
            IP: True,
            TCP: True,
            IPv6: False
        }.get(layer, False)

        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=http_request),
            IP: MagicMock(src="127.0.0.1", dst="127.0.0.1"),
            TCP: MagicMock(sport=54321, dport=8765)
        }[layer]

        packet_callback(mock_pkt)

        # Verify metadata was added
        assert mock_log.called
        logged_entry = mock_log.call_args[0][0]
        assert logged_entry["metadata"] == '{"source": "mcphawk-mcp"}'

    def test_state_isolation_between_tests(self):
        """Test that state is properly isolated between tests."""
        import mcphawk.sniffer
        # Verify state is clean at the start of the test
        assert len(mcphawk.sniffer._mcphawk_mcp_ports) == 0

        # Modify state
        mcphawk.sniffer._mcphawk_mcp_ports.add(9999)

        # State will be cleaned up by setup_method before next test

    @patch('mcphawk.sniffer.log_message')
    @patch('mcphawk.sniffer._broadcast_in_any_loop')
    def test_http_sse_response_parsing(self, mock_broadcast, mock_log):
        """Test parsing of Server-Sent Events (SSE) responses with JSON-RPC."""
        import json

        json_content = json.dumps({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {"name": "get_stats", "description": "Get traffic stats"}
                ]
            },
            "id": 2
        })

        sse_response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/event-stream\r\n"
            f"Cache-Control: no-cache\r\n"
            f"\r\n"
            f"data: {json_content}\n\n"
        ).encode()

        mock_pkt = MagicMock()
        mock_pkt.haslayer.side_effect = lambda layer: layer in [Raw, IP, TCP]
        mock_pkt.__getitem__.side_effect = lambda layer: {
            Raw: MagicMock(load=sse_response),
            IP: MagicMock(src="127.0.0.1", dst="127.0.0.1"),
            TCP: MagicMock(sport=8765, dport=54321)
        }[layer]

        packet_callback(mock_pkt)

        # Verify the JSON-RPC was extracted from SSE format and logged
        assert mock_log.called
        logged_entry = mock_log.call_args[0][0]
        assert logged_entry["message"] == json_content
        assert logged_entry["traffic_type"] == "TCP/Direct"
        assert logged_entry["src_port"] == 8765
        assert logged_entry["dst_port"] == 54321
