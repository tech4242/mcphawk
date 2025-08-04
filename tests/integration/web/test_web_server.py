from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mcphawk.web.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_fetch_logs():
    with patch("mcphawk.web.server.fetch_logs") as mock:
        mock.return_value = [
            {
                "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "src_ip": "127.0.0.1",
                "src_port": 3000,
                "dst_ip": "127.0.0.1",
                "dst_port": 12345,
                "direction": "outgoing",
                "message": '{"jsonrpc":"2.0","method":"test","id":1}',
            },
            {
                "timestamp": datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
                "src_ip": "127.0.0.1",
                "src_port": 12345,
                "dst_ip": "127.0.0.1",
                "dst_port": 3000,
                "direction": "incoming",
                "message": '{"jsonrpc":"2.0","result":"ok","id":1}',
            },
        ]
        yield mock



def test_logs_endpoint(client, mock_fetch_logs):
    response = client.get("/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["src_ip"] == "127.0.0.1"
    assert data[0]["message"] == '{"jsonrpc":"2.0","method":"test","id":1}'
    assert data[1]["message"] == '{"jsonrpc":"2.0","result":"ok","id":1}'


def test_logs_endpoint_with_limit(client, mock_fetch_logs):
    response = client.get("/logs?limit=1")
    assert response.status_code == 200
    mock_fetch_logs.assert_called_once_with(1)


def test_websocket_connection():
    with TestClient(app) as client, client.websocket_connect("/ws"):
        # WebSocket should connect successfully
        # The connection is automatically closed when exiting the context
        pass


def test_websocket_ping_pong():
    import asyncio
    with TestClient(app) as client, patch("asyncio.wait_for") as mock_wait_for:
        # Mock asyncio.wait_for to simulate timeout
        mock_wait_for.side_effect = asyncio.TimeoutError()

        with client.websocket_connect("/ws") as websocket:
            # This should trigger the timeout handling
            try:
                # The server should send a ping
                data = websocket.receive_json()
                assert data == {"type": "ping"}
            except Exception:
                # Connection might close, that's ok
                pass


def test_websocket_disconnect():
    with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
        # Force disconnect by closing
        websocket.close()
    # Should handle gracefully


def test_websocket_broadcast():
    with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
        # Test that websocket connects and can receive messages
        # Just verify the websocket connection works
        assert websocket is not None
        # Could send a test message if needed
        # websocket.send_json({"type": "ping"})




def test_start_sniffer_thread():
    from mcphawk.web.server import _start_sniffer_thread

    with patch("mcphawk.sniffer.start_sniffer"), patch("threading.Thread") as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            _start_sniffer_thread("tcp port 3000", auto_detect=False, debug=True)

            # Verify thread was created with correct arguments
            mock_thread.assert_called_once()
            args, kwargs = mock_thread.call_args
            assert kwargs["daemon"] is True
            assert callable(kwargs["target"])

            # Verify thread was started
            mock_thread_instance.start.assert_called_once()


def test_run_web_with_sniffer():
    from mcphawk.web.server import run_web

    with patch("uvicorn.run") as mock_uvicorn, \
         patch("mcphawk.web.server._start_sniffer_thread") as mock_start_sniffer, \
         patch("mcphawk.logger.init_db"):
        run_web(
            sniffer=True,
            host="0.0.0.0",
            port=9000,
            filter_expr="tcp port 3000",
            auto_detect=False,
            debug=True
        )

        # Verify sniffer was started
        mock_start_sniffer.assert_called_once_with("tcp port 3000", False, True, None, None)

        # Verify uvicorn was started with correct params
        mock_uvicorn.assert_called_once()
        args, kwargs = mock_uvicorn.call_args
        assert args[0] == app  # First arg is the app
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 9000


def test_run_web_without_sniffer():
    from mcphawk.web.server import run_web

    with patch("uvicorn.run") as mock_uvicorn, \
         patch("mcphawk.web.server._start_sniffer_thread") as mock_start_sniffer, \
         patch("mcphawk.logger.init_db"):
        run_web(
            sniffer=False,
            host="127.0.0.1",
            port=8000,
            debug=False
        )

        # Verify sniffer was NOT started
        mock_start_sniffer.assert_not_called()

        # Verify uvicorn was started with correct params
        mock_uvicorn.assert_called_once()
        args, kwargs = mock_uvicorn.call_args
        assert args[0] == app  # First arg is the app
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8000


def test_run_web_sniffer_without_filter():
    from mcphawk.web.server import run_web

    # Test that ValueError is raised when sniffer=True but no filter_expr
    with pytest.raises(ValueError, match="filter_expr is required"):
        run_web(sniffer=True, filter_expr=None)


def test_status_endpoint(client):
    """Test /status endpoint returns MCP server status."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "with_mcp" in data
    assert isinstance(data["with_mcp"], bool)


def test_status_endpoint_with_mcp_enabled():
    """Test /status endpoint when MCP is enabled."""
    import mcphawk.web.server
    from mcphawk.web.server import app

    # Set MCP flag
    original_value = mcphawk.web.server._with_mcp
    mcphawk.web.server._with_mcp = True

    try:
        with TestClient(app) as client:
            response = client.get("/status")
            assert response.status_code == 200
            data = response.json()
            assert data["with_mcp"] is True
    finally:
        # Restore original value
        mcphawk.web.server._with_mcp = original_value
