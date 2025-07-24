import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcphawk.web.broadcaster import active_clients, broadcast_new_log


@pytest.mark.asyncio
async def test_broadcast_new_log_with_clients():
    # Create mock websocket clients
    mock_client1 = AsyncMock()
    mock_client2 = AsyncMock()
    
    # Add to active clients
    active_clients.append(mock_client1)
    active_clients.append(mock_client2)
    
    try:
        # Broadcast a message
        test_log = {
            "timestamp": "2024-01-01T12:00:00Z",
            "src_ip": "127.0.0.1",
            "message": "test"
        }
        
        await broadcast_new_log(test_log)
        
        # Verify both clients received the message
        mock_client1.send_json.assert_called_once_with(test_log)
        mock_client2.send_json.assert_called_once_with(test_log)
        
    finally:
        # Clean up
        active_clients.clear()


@pytest.mark.asyncio
async def test_broadcast_new_log_with_disconnected_client():
    # Create mock websocket clients
    mock_client1 = AsyncMock()
    mock_client2 = AsyncMock()
    
    # Make client1 throw an exception (disconnected)
    mock_client1.send_json.side_effect = Exception("Disconnected")
    
    # Add to active clients
    active_clients.append(mock_client1)
    active_clients.append(mock_client2)
    
    try:
        # Broadcast a message
        test_log = {"test": "data"}
        
        await broadcast_new_log(test_log)
        
        # Client1 should be removed from active_clients
        assert mock_client1 not in active_clients
        assert mock_client2 in active_clients
        
        # Client2 should still receive the message
        mock_client2.send_json.assert_called_once_with(test_log)
        
    finally:
        # Clean up
        active_clients.clear()


@pytest.mark.asyncio 
async def test_broadcast_new_log_no_clients():
    # Ensure list is empty
    active_clients.clear()
    
    # Should not raise any errors
    await broadcast_new_log({"test": "data"})