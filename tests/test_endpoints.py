#!/usr/bin/env python3
"""
Endpoint mapping tests for USDⓈ-M routing (USDT/USDC → fapi/fstream).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.ws_client import MarketDataStream, get_endpoint_prefix, get_listen_key


@pytest.mark.parametrize("quote", ["USDT", "USDC"])
def test_get_endpoint_prefix_um_only(quote: str):
    assert get_endpoint_prefix(quote) == "/fapi"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "env_name,api_base",
    [
        ("testnet", "https://testnet.binancefuture.com"),
        ("prod", "https://fapi.binance.com"),
    ],
)
@pytest.mark.parametrize("quote", ["USDT", "USDC"])
async def test_listen_key_url_um(env_name: str, api_base: str, quote: str):
    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"listenKey": "abc"})

    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_post_cm)

    headers = {"X-MBX-APIKEY": "k"}
    await get_listen_key(mock_session, api_base, headers, quote)

    # Always /fapi on both prod and testnet for UM
    mock_session.post.assert_called_once()
    called_url = mock_session.post.call_args[0][0]
    assert called_url == f"{api_base}/fapi/v1/listenKey"


@pytest.mark.parametrize(
    "env_name,expected_base",
    [
        ("testnet", "wss://stream.binancefuture.com/stream?streams="),
        ("prod", "wss://fstream.binance.com:9443/stream?streams="),
    ],
)
@pytest.mark.parametrize("quote,symbol", [("USDT", "BTC/USDT:USDT"), ("USDC", "BTC/USDC:USDC")])
def test_market_stream_base_um(env_name: str, expected_base: str, quote: str, symbol: str):
    testnet = env_name == "testnet"
    m = MarketDataStream(
        ws_url="", symbols=[symbol], on_price_update=lambda *_: None, resolved_quote_coin=quote, testnet=testnet
    )
    url = m._get_stream_url()
    assert url.startswith(expected_base)
    # Ensure no dstream is present for UM
    assert "dstream" not in url
