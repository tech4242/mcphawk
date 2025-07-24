from typing import Dict, Tuple, List


# Track buffers for fragmented WebSocket messages per connection
ws_buffers: Dict[Tuple[str, int, str, int], bytearray] = {}


def _parse_ws_frames(data: bytes) -> List[str]:
    """
    Parse one or more unmasked WebSocket frames (server->client style).

    Returns complete text messages as a list.
    """
    messages = []
    i = 0
    buffer_len = len(data)

    while i + 2 <= buffer_len:
        first_byte = data[i]
        fin = (first_byte & 0x80) != 0
        opcode = first_byte & 0x0F
        i += 1

        length_byte = data[i]
        masked = (length_byte & 0x80) != 0
        length = length_byte & 0x7F
        i += 1

        if length == 126:
            if i + 2 > buffer_len:
                break
            length = int.from_bytes(data[i:i+2], "big")
            i += 2
        elif length == 127:
            if i + 8 > buffer_len:
                break
            length = int.from_bytes(data[i:i+8], "big")
            i += 8

        if masked:
            # Passive sniffer: ignore masked client->server frames for now
            break

        if i + length > buffer_len:
            break

        payload = data[i:i+length]
        i += length

        # Text or continuation
        if opcode in (0x1, 0x0):
            try:
                msg = payload.decode("utf-8")
                messages.append((fin, msg))
            except UnicodeDecodeError:
                continue

    # Combine fragmented messages (caller handles ordering)
    combined = []
    current = ""
    for fin, part in messages:
        current += part
        if fin:
            combined.append(current)
            current = ""

    return combined


def process_ws_packet(
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    payload: bytes
) -> List[str]:
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
    key = (src_ip, src_port, dst_ip, dst_port)

    if key not in ws_buffers:
        ws_buffers[key] = bytearray()

    ws_buffers[key].extend(payload)
    complete_messages = _parse_ws_frames(ws_buffers[key])

    # Clear buffer if fully consumed (for now, assume messages are atomic)
    if complete_messages:
        ws_buffers[key].clear()

    return [m for m in complete_messages if "jsonrpc" in m]
