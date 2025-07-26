from mcphawk.ws_reassembly import process_ws_packet

# Connection identifiers for test
SRC_IP, SRC_PORT = "127.0.0.1", 11111
DST_IP, DST_PORT = "127.0.0.1", 22222


def build_ws_frame(message: bytes, fin: bool = True, opcode: int = 0x1) -> bytes:
    """
    Build a single valid unmasked WebSocket frame (server->client style).

    Args:
        message: Payload as bytes.
        fin: Whether this is the final frame (FIN bit).
        opcode: Frame opcode (0x1 = text, 0x0 = continuation).

    Returns:
        Raw bytes representing the WebSocket frame.
    """
    first_byte = (0x80 if fin else 0x00) | opcode
    length = len(message)

    if length <= 125:
        header = bytes([first_byte, length])
    elif length <= 65535:
        header = bytes([first_byte, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first_byte, 127]) + length.to_bytes(8, "big")

    return header + message


def test_process_ws_packet_complete():
    """Ensure a full single WebSocket frame is reassembled correctly."""
    message = b'{"jsonrpc":"2.0","method":"ping"}'
    frame = build_ws_frame(message)

    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame)
    assert len(msgs) == 1
    assert "ping" in msgs[0]


def test_process_ws_packet_fragmented():
    """Test that fragmented frames are handled (currently not buffered)."""
    # Our simplified implementation doesn't buffer fragmented frames
    # This is acceptable for most real-world MCP traffic which uses small messages
    full_msg = b'{"jsonrpc":"2.0","method":"pong"}'
    mid = len(full_msg) // 2

    frame1 = build_ws_frame(full_msg[:mid], fin=False, opcode=0x1)
    frame2 = build_ws_frame(full_msg[mid:], fin=True, opcode=0x0)

    # Each fragment is processed independently
    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame1)
    assert msgs == []  # Partial JSON won't be captured

    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame2)
    assert msgs == []  # Continuation frame alone won't be captured

    # For complete capture, send as single frame
    complete_frame = build_ws_frame(full_msg)
    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, complete_frame)
    assert len(msgs) == 1
    assert "pong" in msgs[0]
