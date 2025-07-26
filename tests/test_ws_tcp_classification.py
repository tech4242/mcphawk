"""Test that WebSocket and TCP traffic are correctly classified."""
import json
import time

import pytest
from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

from mcphawk.logger import clear_logs, fetch_logs, init_db, set_db_path
from mcphawk.sniffer import packet_callback


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_ws_tcp_class.db"
    set_db_path(str(db_path))
    init_db()
    yield db_path
    clear_logs()


def test_websocket_http_upgrade_not_misclassified(test_db):
    """Test that WebSocket HTTP upgrade is not classified as TCP JSON-RPC."""
    # Create HTTP upgrade packet
    http_upgrade = (
        b"GET / HTTP/1.1\r\n"
        b"Host: localhost:8765\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==\r\n"
        b"Sec-WebSocket-Version: 13\r\n\r\n"
    )

    pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=50000, dport=8765) / Raw(load=http_upgrade)
    packet_callback(pkt)

    time.sleep(0.1)

    # Should not create any log entries (HTTP upgrade is not JSON-RPC)
    logs = fetch_logs(limit=10)
    assert len(logs) == 0


def test_websocket_empty_frame_not_misclassified(test_db):
    """Test that incomplete WebSocket frames are not classified as TCP."""
    # Send part of a WebSocket frame (incomplete)
    partial_frame = bytes([0x81, 0x7e, 0x00])  # Text frame header, but incomplete

    pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=50001, dport=8765) / Raw(load=partial_frame)
    packet_callback(pkt)

    time.sleep(0.1)

    # Should not create any entries (incomplete frame, no JSON-RPC)
    logs = fetch_logs(limit=10)
    assert len(logs) == 0


def test_websocket_complete_frame_classified_correctly(test_db):
    """Test that complete WebSocket frames are classified as WS."""
    # Create a complete WebSocket text frame with JSON-RPC
    json_rpc = json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1})
    frame = bytes([0x81, len(json_rpc)]) + json_rpc.encode()

    pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=50002, dport=8765) / Raw(load=frame)
    packet_callback(pkt)

    time.sleep(0.1)

    logs = fetch_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["traffic_type"] == "TCP/WS"
    assert "test" in logs[0]["message"]


def test_tcp_jsonrpc_classified_correctly(test_db):
    """Test that raw TCP JSON-RPC is classified as TCP."""
    json_rpc = json.dumps({"jsonrpc": "2.0", "method": "tcp_test", "id": 1})

    pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=12345, dport=50003) / Raw(load=json_rpc.encode())
    packet_callback(pkt)

    time.sleep(0.1)

    logs = fetch_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["traffic_type"] == "TCP/Direct"
    assert "tcp_test" in logs[0]["message"]


def test_mixed_traffic_correct_classification(test_db):
    """Test that mixed TCP and WebSocket traffic is correctly classified."""
    # Send TCP JSON-RPC
    tcp_msg = json.dumps({"jsonrpc": "2.0", "method": "tcp_method", "id": 1})
    tcp_pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=12345, dport=50004) / Raw(load=tcp_msg.encode())
    packet_callback(tcp_pkt)

    # Send WebSocket frame
    ws_msg = json.dumps({"jsonrpc": "2.0", "method": "ws_method", "id": 2})
    ws_frame = bytes([0x81, len(ws_msg)]) + ws_msg.encode()
    ws_pkt = IP(src="127.0.0.1", dst="127.0.0.1") / TCP(sport=50005, dport=8765) / Raw(load=ws_frame)
    packet_callback(ws_pkt)

    time.sleep(0.1)

    logs = fetch_logs(limit=10)
    assert len(logs) == 2

    # Check each log
    tcp_log = next((log for log in logs if "tcp_method" in log["message"]), None)
    ws_log = next((log for log in logs if "ws_method" in log["message"]), None)

    assert tcp_log is not None
    assert tcp_log["traffic_type"] == "TCP/Direct"

    assert ws_log is not None
    assert ws_log["traffic_type"] == "TCP/WS"
