# Track buffers for fragmented WebSocket messages per connection
ws_buffers: dict[tuple[str, int, str, int], bytearray] = {}


def _parse_ws_frames(data: bytes) -> tuple[list[tuple[bool, str]], int]:
    """
    Parse one or more WebSocket frames.

    Returns (messages, consumed_bytes) where messages is a list of (fin, text) tuples.
    """
    messages = []
    i = 0
    buffer_len = len(data)

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Parsing WebSocket frames from {buffer_len} bytes")

    while i < buffer_len:
        start_pos = i  # Remember where this frame started

        # Need at least 2 bytes for header
        if i + 2 > buffer_len:
            break

        first_byte = data[i]
        fin = (first_byte & 0x80) != 0
        opcode = first_byte & 0x0F
        i += 1

        length_byte = data[i]
        masked = (length_byte & 0x80) != 0
        length = length_byte & 0x7F
        i += 1

        # Extended length handling
        if length == 126:
            if i + 2 > buffer_len:
                i = start_pos  # Reset to frame start
                break
            length = int.from_bytes(data[i:i+2], "big")
            i += 2
        elif length == 127:
            if i + 8 > buffer_len:
                i = start_pos  # Reset to frame start
                break
            length = int.from_bytes(data[i:i+8], "big")
            i += 8

        # Check if we have the complete frame
        if masked:
            if i + 4 + length > buffer_len:
                i = start_pos  # Reset to frame start
                break
            mask = data[i:i+4]
            i += 4

            payload = bytearray(data[i:i+length])
            # Unmask the payload
            for j in range(length):
                payload[j] ^= mask[j % 4]
            i += length
        else:
            if i + length > buffer_len:
                i = start_pos  # Reset to frame start
                break
            payload = data[i:i+length]
            i += length

        # Process the payload based on opcode
        if opcode == 0x1:  # Text frame
            try:
                msg = payload.decode("utf-8")
                messages.append((fin, msg))
                logger.debug(f"Decoded text frame: {msg[:100]}...")
            except UnicodeDecodeError:
                logger.debug("Failed to decode text frame")
                continue
        elif opcode == 0x0:  # Continuation frame
            try:
                msg = payload.decode("utf-8")
                messages.append((fin, msg))
            except UnicodeDecodeError:
                continue

    return messages, i


def process_ws_packet(
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    payload: bytes
) -> list[str]:
    """
    Process TCP payloads and reconstruct WebSocket text messages.

    Args:
        src_ip: Source IP address.
        src_port: Source port.
        dst_ip: Destination IP address.
        dst_port: Destination port.
        payload: Raw TCP payload bytes.

    Returns:
        List of completed JSON strings (if any).
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Processing WS packet from {src_ip}:{src_port} to {dst_ip}:{dst_port}, {len(payload)} bytes")

    # Check if this is HTTP upgrade request/response
    if payload.startswith(b'GET ') or payload.startswith(b'HTTP/'):
        logger.debug("Detected HTTP upgrade, skipping frame parsing")
        return []

    key = (src_ip, src_port, dst_ip, dst_port)

    if key not in ws_buffers:
        ws_buffers[key] = bytearray()

    # Append new data to buffer
    ws_buffers[key].extend(payload)
    logger.debug(f"Buffer size for {key}: {len(ws_buffers[key])} bytes")

    # Try to parse all complete frames from the buffer
    try:
        parsed_messages, consumed = _parse_ws_frames(bytes(ws_buffers[key]))

        # Remove consumed bytes from buffer
        if consumed > 0:
            ws_buffers[key] = ws_buffers[key][consumed:]
            logger.debug(f"Consumed {consumed} bytes, {len(ws_buffers[key])} bytes remain in buffer")

        # Extract complete messages from parsed frames
        combined = []
        current = ""
        for fin, part in parsed_messages:
            current += part
            if fin:
                combined.append(current)
                current = ""

        # Filter for JSON-RPC messages
        json_messages = [m for m in combined if "jsonrpc" in m]
        if json_messages:
            logger.debug(f"Found {len(json_messages)} JSON-RPC messages")

        # Clean up large buffers to prevent memory issues
        if len(ws_buffers[key]) > 1024 * 1024:  # 1MB limit
            logger.warning(f"Buffer for {key} exceeded 1MB, clearing")
            ws_buffers[key] = bytearray()

        return json_messages

    except Exception as e:
        logger.error(f"Error parsing WebSocket frames: {e}")
        # Clear buffer on error to recover
        ws_buffers[key] = bytearray()
        return []

