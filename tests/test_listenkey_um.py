#!/usr/bin/env python3
import asyncio
from types import SimpleNamespace

import pytest

from core.ws_client import build_listenkey_url, get_listen_key


def test_build_listenkey_url_prod_um():
    url = build_listenkey_url(testnet=False)
    assert url.startswith("https://fapi.binance.com/")
    assert "/fapi/v1/listenKey" in url
    assert "dapi" not in url


def test_build_listenkey_url_testnet_um():
    url = build_listenkey_url(testnet=True)
    assert url.startswith("https://testnet.binancefuture.com/")
    assert "/fapi/v1/listenKey" in url
    assert "dapi" not in url


@pytest.mark.asyncio
async def test_get_listen_key_uses_um_endpoint(monkeypatch):
    """
    Contract test: get_listen_key must hit the UM (fapi) listenKey URL
    for both USDT and USDC. We inject a fake http_client and capture the URL.
    """
    captured = {}

    async def fake_post(url, *_, **__):
        captured["url"] = url
        return SimpleNamespace(status=200, json=lambda: {"listenKey": "abc"})

    class FakeResponse:
        def __init__(self, data: dict):
            self._data = data
            self.status = 200

        async def json(self):
            return self._data

    class FakeCM:
        def __init__(self, data: dict):
            self._resp = FakeResponse(data)

        async def __aenter__(self):
            return self._resp

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        def post(self, url, *_, **__):
            captured["url"] = url
            return FakeCM({"listenKey": "abc"})

    fake_session = FakeSession()

    # USDC / prod
    key = await get_listen_key(fake_session, "https://fapi.binance.com", {"X-MBX-APIKEY": "k"}, "USDC")
    assert key == "abc"
    assert captured["url"].startswith("https://fapi.binance.com/")
    assert "/fapi/v1/listenKey" in captured["url"]
    assert "dapi" not in captured["url"]

    # USDT / testnet
    key = await get_listen_key(fake_session, "https://testnet.binancefuture.com", {"X-MBX-APIKEY": "k"}, "USDT")
    assert key == "abc"
    assert captured["url"].startswith("https://testnet.binancefuture.com/")
    assert "/fapi/v1/listenKey" in captured["url"]
    assert "dapi" not in captured["url"]
