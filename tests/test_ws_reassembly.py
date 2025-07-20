from mcp_shark.ws_reassembly import process_ws_packet

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
    message = '{"jsonrpc":"2.0","method":"ping"}'.encode()
    frame = build_ws_frame(message)

    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame)
    assert len(msgs) == 1
    assert "ping" in msgs[0]


def test_process_ws_packet_fragmented():
    """Ensure fragmented WebSocket frames are reassembled correctly."""
    full_msg = '{"jsonrpc":"2.0","method":"pong"}'.encode()
    mid = len(full_msg) // 2

    frame1 = build_ws_frame(full_msg[:mid], fin=False, opcode=0x1)
    frame2 = build_ws_frame(full_msg[mid:], fin=True, opcode=0x0)

    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame1)
    assert msgs == []  # No complete message yet

    msgs = process_ws_packet(SRC_IP, SRC_PORT, DST_IP, DST_PORT, frame2)
    assert len(msgs) == 1
    assert "pong" in msgs[0]
