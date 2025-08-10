#!/usr/bin/env python3
"""
Stage E: Unit tests for WebSocket/User Data functionality.
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Fix for Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.ws_client import UserDataStreamManager, get_listen_key, keepalive, stream_user_data


@pytest.mark.asyncio
async def test_get_listen_key():
    """Test get_listen_key function."""

    # Mock response data
    mock_listen_key = "test_listen_key_123456"
    mock_response_data = {"listenKey": mock_listen_key}

    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_response_data)

    # Create mock context manager for post
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)

    # Test parameters
    api_base = "https://testnet.binancefuture.com"
    headers = {"X-MBX-APIKEY": "test_api_key"}

    # Call the function
    result = await get_listen_key(mock_session, api_base, headers)

    # Assertions
    assert result == mock_listen_key
    mock_session.post.assert_called_once_with(f"{api_base}/fapi/v1/listenKey", headers=headers)


@pytest.mark.asyncio
async def test_get_listen_key_error():
    """Test get_listen_key with error response."""

    # Create mock error response
    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text = AsyncMock(return_value="Bad Request")

    # Create mock context manager for post
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)

    # Test parameters
    api_base = "https://testnet.binancefuture.com"
    headers = {"X-MBX-APIKEY": "test_api_key"}

    # Call should raise exception
    with pytest.raises(Exception) as exc_info:
        await get_listen_key(mock_session, api_base, headers)

    assert "Failed to get listen key" in str(exc_info.value)


@pytest.mark.asyncio
async def test_keepalive():
    """Test keepalive function."""

    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 200

    # Create mock context manager for put
    mock_put_cm = AsyncMock()
    mock_put_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_put_cm.__aexit__ = AsyncMock(return_value=None)

    # Create mock session
    mock_session = AsyncMock()
    mock_session.put = MagicMock(return_value=mock_put_cm)

    # Test parameters
    api_base = "https://testnet.binancefuture.com"
    headers = {"X-MBX-APIKEY": "test_api_key"}
    listen_key = "test_listen_key"

    # Call the function
    await keepalive(mock_session, api_base, headers, listen_key)

    # Assertions
    mock_session.put.assert_called_once_with(
        f"{api_base}/fapi/v1/listenKey", headers=headers, params={"listenKey": listen_key}
    )


@pytest.mark.asyncio
async def test_stream_user_data_event_handling():
    """Test stream_user_data event handling."""

    # Create mock WebSocket message
    test_event = {"e": "ORDER_TRADE_UPDATE", "o": {"s": "BTCUSDT", "S": "BUY", "X": "FILLED"}}

    mock_msg = MagicMock()
    mock_msg.type = MagicMock()
    mock_msg.type.name = "TEXT"
    mock_msg.data = json.dumps(test_event)

    # Track event handler calls
    events_received = []

    def mock_on_event(event):
        events_received.append(event)

    # Mock aiohttp WebSocket
    with patch("aiohttp.ClientSession") as mock_client_session:
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = AsyncMock(return_value=[mock_msg].__iter__())

        # Create mock context manager for ws_connect
        mock_ws_cm = AsyncMock()
        mock_ws_cm.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.ws_connect = MagicMock(return_value=mock_ws_cm)

        # Create mock context manager for ClientSession
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client_session.return_value = mock_session_cm

        # Monkeypatch to make the message type check work
        import aiohttp

        mock_msg.type = aiohttp.WSMsgType.TEXT

        # Run stream_user_data for a short time
        task = asyncio.create_task(
            stream_user_data(
                "wss://stream.binancefuture.com",
                "test_listen_key",
                mock_on_event,
                ws_reconnect_interval=5,
                ws_heartbeat_interval=30,
            )
        )

        # Let it process the message
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check that event was received
        assert len(events_received) == 1
        assert events_received[0] == test_event


@pytest.mark.asyncio
async def test_user_data_stream_manager():
    """Test UserDataStreamManager class."""

    # Create mock event handler
    events_received = []

    def mock_on_event(event):
        events_received.append(event)

    # Create manager
    manager = UserDataStreamManager(
        api_base="https://testnet.binancefuture.com",
        ws_url="wss://stream.binancefuture.com",
        api_key="test_api_key",
        on_event=mock_on_event,
        ws_reconnect_interval=5,
        ws_heartbeat_interval=30,
    )

    # Mock the internal methods
    with patch.object(manager, "_keepalive_loop", new_callable=AsyncMock) as mock_keepalive:
        with patch("core.ws_client.get_listen_key", new_callable=AsyncMock) as mock_get_key:
            with patch("core.ws_client.stream_user_data", new_callable=AsyncMock) as mock_stream:
                mock_get_key.return_value = "test_listen_key"

                # Start the manager
                await manager.start()

                # Check that components were initialized
                assert manager.listen_key == "test_listen_key"
                assert manager.http_session is not None
                assert manager.keepalive_task is not None
                assert manager.stream_task is not None

                # Stop the manager
                await manager.stop()

                # Check cleanup
                assert manager.keepalive_task.cancelled()
                assert manager.stream_task.cancelled()


@pytest.mark.asyncio
async def test_event_handler_account_update():
    """Test handling of ACCOUNT_UPDATE events."""
    from core.ws_client import log_event_handler

    # Create test ACCOUNT_UPDATE event
    test_event = {
        "e": "ACCOUNT_UPDATE",
        "a": {
            "B": [{"a": "USDT", "wb": "100.0", "cw": "100.0"}],
            "P": [{"s": "BTCUSDT", "pa": "0.001", "ep": "50000", "up": "5.0"}],
        },
    }

    # Call handler (just checking it doesn't raise)
    log_event_handler(test_event)


@pytest.mark.asyncio
async def test_event_handler_order_update():
    """Test handling of ORDER_TRADE_UPDATE events."""
    from core.ws_client import log_event_handler

    # Create test ORDER_TRADE_UPDATE event
    test_event = {
        "e": "ORDER_TRADE_UPDATE",
        "o": {"s": "BTCUSDT", "S": "BUY", "o": "LIMIT", "X": "FILLED", "i": "123456", "p": "50000", "q": "0.001"},
    }

    # Call handler (just checking it doesn't raise)
    log_event_handler(test_event)


@pytest.mark.asyncio
async def test_listen_key_expired_handler():
    """Test handling of listenKeyExpired event."""
    from core.ws_client import log_event_handler

    # Create test listenKeyExpired event
    test_event = {"e": "listenKeyExpired"}

    # Call handler (just checking it doesn't raise)
    log_event_handler(test_event)


def test_stage_e_structure():
    """Test that Stage E components are properly structured."""

    # Import all Stage E components
    from core.ws_client import (UserDataStreamManager, get_listen_key, keepalive, log_event_handler,
                                stream_user_data)

    # Check that all required functions exist
    assert callable(get_listen_key)
    assert callable(keepalive)
    assert callable(stream_user_data)
    assert callable(log_event_handler)

    # Check UserDataStreamManager has required methods
    assert hasattr(UserDataStreamManager, "start")
    assert hasattr(UserDataStreamManager, "stop")
    assert hasattr(UserDataStreamManager, "_keepalive_loop")

    print("✅ Stage E structure test passed!")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
