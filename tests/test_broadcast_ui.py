"""
Test broadcasting logs to the UI by injecting fake packets into the sniffer.

This ensures:
- Packets are logged in the database.
- Broadcast messages are handled without errors.
"""

import json
import os

from scapy.all import IP, TCP, Ether, Raw

from mcphawk.logger import clear_logs, fetch_logs, init_db, set_db_path
from mcphawk.sniffer import packet_callback

TEST_DB = "test_mcphawk_logs.db"


def setup_module(module):
    """Ensure we use a clean test database before running tests."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    set_db_path(TEST_DB)
    init_db()
    clear_logs()


def teardown_module(module):
    """Clean up the test database after tests."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def build_fake_packet(message: str):
    """Helper to build a fake TCP packet with a JSON-RPC message."""
    return (
        Ether()
        / IP(src="127.0.0.1", dst="127.0.0.1")
        / TCP(sport=55555, dport=12345)
        / Raw(load=message.encode())
    )


def test_broadcast_ui_injection():
    """
    Inject several fake packets and verify:
    - They are logged in the database.
    - No exceptions occur during broadcasting.
    """
    messages = [
        '{"jsonrpc":"2.0","method":"ping"}',
        '{"jsonrpc":"2.0","method":"pong"}',
        '{"jsonrpc":"2.0","method":"statusCheck"}',
    ]

    for i, msg in enumerate(messages, 1):
        print(f"[TEST] Injecting fake packet #{i}: {json.loads(msg)['method']}")
        pkt = build_fake_packet(msg)
        packet_callback(pkt)

    # Fetch logs from DB and verify
    logs = fetch_logs(limit=10)
    assert len(logs) >= 3, f"Expected at least 3 logs, got {len(logs)}"
    assert any("ping" in log["message"] for log in logs)
    assert any("pong" in log["message"] for log in logs)

    print(f"[TEST] Logs fetched: {logs}")


if __name__ == "__main__":
    # Run manually if needed
    setup_module(None)
    test_broadcast_ui_injection()
    teardown_module(None)
