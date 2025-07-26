"""Simple WebSocket parsing tests without full integration."""

import json

from mcphawk.ws_reassembly import _parse_ws_frames, process_ws_packet, ws_buffers


class TestWebSocketParsing:
    """Test WebSocket frame parsing without network integration."""

    def test_parse_unmasked_text_frame(self):
        """Test parsing unmasked text frame (server->client)."""
        text = '{"jsonrpc":"2.0","method":"test","id":1}'
        payload = text.encode('utf-8')

        # Build WebSocket frame
        frame = bytearray()
        frame.append(0x81)  # FIN=1, opcode=1 (text)
        frame.append(len(payload))  # No mask
        frame.extend(payload)

        messages, consumed = _parse_ws_frames(bytes(frame))
        assert len(messages) == 1
        assert messages[0][1] == text  # messages are (fin, text) tuples
        assert consumed == len(frame)

    def test_parse_masked_text_frame(self):
        """Test parsing masked text frame (client->server)."""
        text = '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
        payload = text.encode('utf-8')

        # Build masked WebSocket frame
        frame = bytearray()
        frame.append(0x81)  # FIN=1, opcode=1 (text)
        frame.append(0x80 | len(payload))  # Masked bit + length

        # Add masking key
        mask = b'\x12\x34\x56\x78'
        frame.extend(mask)

        # Mask the payload
        masked_payload = bytearray()
        for i, byte in enumerate(payload):
            masked_payload.append(byte ^ mask[i % 4])
        frame.extend(masked_payload)

        messages, consumed = _parse_ws_frames(bytes(frame))
        assert len(messages) == 1
        assert messages[0][1] == text  # messages are (fin, text) tuples
        assert consumed == len(frame)

    def test_parse_fragmented_frames(self):
        """Test parsing fragmented WebSocket frames."""
        # First fragment
        part1 = '{"jsonrpc":"2.0",'
        frame1 = bytearray()
        frame1.append(0x01)  # FIN=0, opcode=1 (text)
        frame1.append(len(part1))
        frame1.extend(part1.encode('utf-8'))

        # Final fragment
        part2 = '"method":"test","id":1}'
        frame2 = bytearray()
        frame2.append(0x80)  # FIN=1, opcode=0 (continuation)
        frame2.append(len(part2))
        frame2.extend(part2.encode('utf-8'))

        messages, consumed = _parse_ws_frames(bytes(frame1 + frame2))
        assert len(messages) == 2  # Two fragments
        assert messages[0][1] == part1
        assert messages[1][1] == part2

    def test_process_ws_packet_filters_jsonrpc(self):
        """Test that process_ws_packet filters for JSON-RPC messages."""
        # Clear any existing buffers
        ws_buffers.clear()

        # JSON-RPC message
        jsonrpc_text = '{"jsonrpc":"2.0","method":"test","id":1}'
        jsonrpc_frame = bytearray()
        jsonrpc_frame.append(0x81)
        jsonrpc_frame.append(len(jsonrpc_text))
        jsonrpc_frame.extend(jsonrpc_text.encode('utf-8'))

        # Non-JSON-RPC message
        other_text = '{"type":"hello","data":"world"}'
        other_frame = bytearray()
        other_frame.append(0x81)
        other_frame.append(len(other_text))
        other_frame.extend(other_text.encode('utf-8'))

        # Process JSON-RPC frame
        messages = process_ws_packet("127.0.0.1", 12345, "127.0.0.1", 8765, bytes(jsonrpc_frame))
        assert len(messages) == 1
        assert json.loads(messages[0])["jsonrpc"] == "2.0"

        # Process non-JSON-RPC frame
        messages = process_ws_packet("127.0.0.1", 12345, "127.0.0.1", 8765, bytes(other_frame))
        assert len(messages) == 0

    def test_process_ws_packet_skips_http_upgrade(self):
        """Test that HTTP upgrade requests are skipped."""
        http_request = b'GET /ws HTTP/1.1\r\nUpgrade: websocket\r\n\r\n'
        messages = process_ws_packet("127.0.0.1", 12345, "127.0.0.1", 8765, http_request)
        assert len(messages) == 0

        http_response = b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n'
        messages = process_ws_packet("127.0.0.1", 8765, "127.0.0.1", 12345, http_response)
        assert len(messages) == 0

    def test_multiple_frames_in_one_packet(self):
        """Test parsing multiple frames in one TCP packet."""
        # First message
        msg1 = '{"jsonrpc":"2.0","method":"ping","id":1}'
        frame1 = bytearray()
        frame1.append(0x81)
        frame1.append(len(msg1))
        frame1.extend(msg1.encode('utf-8'))

        # Second message
        msg2 = '{"jsonrpc":"2.0","result":"pong","id":1}'
        frame2 = bytearray()
        frame2.append(0x81)
        frame2.append(len(msg2))
        frame2.extend(msg2.encode('utf-8'))

        # Parse both frames together
        messages, consumed = _parse_ws_frames(bytes(frame1 + frame2))
        assert len(messages) == 2
        assert messages[0][1] == msg1
        assert messages[1][1] == msg2
