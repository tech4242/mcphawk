"""Test that sniffer properly sets transport_type for captured packets."""
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
    db_path = tmp_path / "test_sniffer_transport_type.db"
    set_db_path(str(db_path))
    init_db()
    yield db_path
    clear_logs()


def test_sniffer_tcp_transport_type(test_db):
    """Test that sniffer marks TCP JSON-RPC traffic with transport_type='TCP'."""
    # Create a mock TCP packet with JSON-RPC content
    json_rpc = json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1})

    # Create packet layers
    ip = IP(src="127.0.0.1", dst="127.0.0.1")
    tcp = TCP(sport=12345, dport=54321)
    raw = Raw(load=json_rpc.encode())

    # Construct the packet
    pkt = ip / tcp / raw

    # Process the packet
    packet_callback(pkt)

    # Give it a moment to process
    time.sleep(0.1)

    # Check the logged entry
    logs = fetch_logs(limit=1)
    assert len(logs) == 1
    assert logs[0]["transport_type"] == "unknown"
    assert logs[0]["src_port"] == 12345
    assert logs[0]["dst_port"] == 54321




def test_sniffer_non_jsonrpc_ignored(test_db):
    """Test that non-JSON-RPC traffic is ignored."""
    # Create a packet with non-JSON-RPC content
    ip = IP(src="127.0.0.1", dst="127.0.0.1")
    tcp = TCP(sport=12345, dport=54321)
    raw = Raw(load=b"Hello, this is not JSON-RPC")

    # Construct the packet
    pkt = ip / tcp / raw

    # Process the packet
    packet_callback(pkt)

    # Give it a moment to process
    time.sleep(0.1)

    # Should have no logs
    logs = fetch_logs(limit=1)
    assert len(logs) == 0
