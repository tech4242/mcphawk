"""Integration tests for WebSocket MCP capture."""

import contextlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from scapy.all import IP, TCP, Raw

from mcphawk import logger
from mcphawk.sniffer import packet_callback
from mcphawk.ws_reassembly import ws_buffers


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Set up the database
    original_path = getattr(logger, 'DB_PATH', None)
    logger.set_db_path(db_path)
    logger.init_db()

    # Also update the module variable directly
    import mcphawk.logger as logger_module
    logger_module.DB_PATH = Path(db_path)

    yield db_path

    # Cleanup
    with contextlib.suppress(OSError):
        os.unlink(db_path)

    # Restore original path if it existed
    if original_path:
        logger.DB_PATH = original_path
        logger_module.DB_PATH = original_path


def create_ws_text_frame(text):
    """Create a WebSocket text frame."""
    frame = bytearray()
    frame.append(0x81)  # FIN=1, opcode=1 (text)
    payload = text.encode('utf-8')

    if len(payload) < 126:
        frame.append(len(payload))
    elif len(payload) < 65536:
        frame.append(126)
        frame.extend(len(payload).to_bytes(2, 'big'))
    else:
        frame.append(127)
        frame.extend(len(payload).to_bytes(8, 'big'))

    frame.extend(payload)
    return bytes(frame)


def create_mock_packet(src_ip, src_port, dst_ip, dst_port, payload):
    """Create a mock Scapy packet."""
    mock_packet = Mock()

    # Mock Raw layer
    mock_raw = Mock()
    mock_raw.load = payload

    # Mock TCP layer
    mock_tcp = Mock()
    mock_tcp.sport = src_port
    mock_tcp.dport = dst_port

    # Mock IP layer
    mock_ip = Mock()
    mock_ip.src = src_ip
    mock_ip.dst = dst_ip

    # Setup haslayer
    def haslayer(layer_type):
        return layer_type in (Raw, TCP, IP)

    mock_packet.haslayer = haslayer

    # Setup getitem
    def getitem(self, layer_type):
        if layer_type == Raw:
            return mock_raw
        elif layer_type == TCP:
            return mock_tcp
        elif layer_type == IP:
            return mock_ip
        raise KeyError(f"No layer {layer_type}")

    mock_packet.__getitem__ = getitem

    return mock_packet


def test_websocket_capture_simple(temp_db):
    """Test basic WebSocket frame capture."""
    # Create WebSocket frames
    msg1 = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
    msg2 = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 1}

    frame1 = create_ws_text_frame(json.dumps(msg1))
    frame2 = create_ws_text_frame(json.dumps(msg2))

    # Create mock packets
    packet1 = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, frame1)
    packet2 = create_mock_packet("127.0.0.1", 8765, "127.0.0.1", 12345, frame2)

    # Process packets
    packet_callback(packet1)
    packet_callback(packet2)

    # Check database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs ORDER BY timestamp")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2

    # Check first message
    msg = json.loads(rows[0][0])
    assert msg["method"] == "initialize"
    assert msg["id"] == 1

    # Check second message
    msg = json.loads(rows[1][0])
    assert msg["result"]["status"] == "ok"
    assert msg["id"] == 1


def test_websocket_capture_with_notification(temp_db):
    """Test WebSocket capture with notifications (no ID)."""
    # Create frames
    request = {"jsonrpc": "2.0", "method": "ping", "id": 1}
    response = {"jsonrpc": "2.0", "result": "pong", "id": 1}
    notification = {"jsonrpc": "2.0", "method": "status/update", "params": {"value": 42}}

    frames = [
        create_ws_text_frame(json.dumps(request)),
        create_ws_text_frame(json.dumps(response)),
        create_ws_text_frame(json.dumps(notification)),
    ]

    # Process all frames
    for frame in frames:
        packet = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, frame)
        packet_callback(packet)

    # Check database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 3

    messages = [json.loads(row[0]) for row in rows]

    # Check we have the notification
    notifications = [msg for msg in messages if "method" in msg and "id" not in msg]
    assert len(notifications) == 1
    assert notifications[0]["method"] == "status/update"


def test_websocket_capture_large_message(temp_db):
    """Test WebSocket capture with large messages requiring extended length."""
    # Create a large message
    large_data = {"jsonrpc": "2.0", "method": "data", "params": {"value": "x" * 1000}, "id": 1}
    frame = create_ws_text_frame(json.dumps(large_data))

    packet = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, frame)
    packet_callback(packet)

    # Check database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    msg = json.loads(rows[0][0])
    assert msg["method"] == "data"
    assert len(msg["params"]["value"]) == 1000


def test_websocket_tcp_segmentation(temp_db):
    """Test handling of WebSocket frames split across TCP packets."""
    # Clear buffers
    ws_buffers.clear()

    # Create a message
    msg = {"jsonrpc": "2.0", "method": "test", "id": 1}
    frame = create_ws_text_frame(json.dumps(msg))

    # Split frame into two packets
    split_point = len(frame) // 2
    packet1 = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, frame[:split_point])
    packet2 = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, frame[split_point:])

    # Process both packets
    print(f"\nProcessing split frame: {len(frame)} bytes total")
    print(f"Part 1: {len(frame[:split_point])} bytes")
    print(f"Part 2: {len(frame[split_point:])} bytes")

    packet_callback(packet1)
    packet_callback(packet2)

    # Check database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs")
    rows = cursor.fetchall()
    conn.close()

    # Should have reassembled into one message
    assert len(rows) == 1
    msg = json.loads(rows[0][0])
    assert msg["method"] == "test"


def test_websocket_multiple_frames_in_packet(temp_db):
    """Test multiple WebSocket frames in one TCP packet."""
    # Clear buffers
    ws_buffers.clear()

    # Create multiple messages
    msg1 = {"jsonrpc": "2.0", "method": "ping", "id": 1}
    msg2 = {"jsonrpc": "2.0", "method": "ping", "id": 2}

    frame1 = create_ws_text_frame(json.dumps(msg1))
    frame2 = create_ws_text_frame(json.dumps(msg2))

    # Combine frames into one packet
    combined = frame1 + frame2
    packet = create_mock_packet("127.0.0.1", 12345, "127.0.0.1", 8765, combined)
    packet_callback(packet)

    # Check database
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs ORDER BY timestamp")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2

    msg1_db = json.loads(rows[0][0])
    msg2_db = json.loads(rows[1][0])

    assert msg1_db["id"] == 1
    assert msg2_db["id"] == 2

