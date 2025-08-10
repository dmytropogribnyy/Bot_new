#!/usr/bin/env python3
import asyncio
from pathlib import Path

import pytest

from core.idempotency_store import IdempotencyStore
from core.ids import make_client_id
from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger
from core.order_manager import OrderManager


def test_same_intent_persists(tmp_path: Path):
    store_path = tmp_path / "idem.json"
    store = IdempotencyStore(str(store_path))
    store.load()

    intent = "ENV|STRAT|BTCUSDT|BUY|MARKET|1|MKT||"
    cid1 = make_client_id("PROD", "S1", "BTC/USDT", "BUY", intent, ts_ms=1700000000000)
    store.put(intent, cid1)
    assert store.get(intent) == cid1

    # Reload from disk should persist
    store.load()
    assert store.get(intent) == cid1


def test_make_client_id_length_and_charset():
    cid = make_client_id("prod!!", "strat++", "xrp/usdt", "buy", "intent with spaces///---")
    assert len(cid) <= 36


@pytest.mark.asyncio
async def test_cleanup_stray_orders(tmp_path: Path, monkeypatch):
    # Minimal config and logger
    config = TradingConfig()
    logger = UnifiedLogger(config)

    # Stub exchange with required async methods
    class StubExchange:
        def __init__(self):
            self.cancelled = []

        async def fetch_open_orders(self, symbol):
            return [
                {
                    "id": "tp1",
                    "reduceOnly": True,
                    "info": {"reduceOnly": True},
                }
            ]

        async def fetch_position(self, symbol):
            return {"symbol": symbol, "contracts": 0}

        async def cancel_order(self, order_id, symbol):
            self.cancelled.append((order_id, symbol))
            return {"status": "canceled", "id": order_id, "symbol": symbol}

    # Wire into OptimizedExchangeClient methods used by OrderManager
    ex = OptimizedExchangeClient(config, logger)
    stub = StubExchange()

    async def get_open_orders(sym=None):
        return await stub.fetch_open_orders(sym)

    async def get_position(sym):
        return await stub.fetch_position(sym)

    async def cancel_order(order_id, sym):
        return await stub.cancel_order(order_id, sym)

    ex.get_open_orders = get_open_orders  # type: ignore[attr-defined]
    ex.get_position = get_position  # type: ignore[attr-defined]
    ex.cancel_order = cancel_order  # type: ignore[attr-defined]

    om = OrderManager(config, ex, logger)
    res = await om.startup_cleanup(["BTC/USDT:USDT"])

    assert res["cancelled"] >= 1
    assert ("tp1", "BTC/USDT:USDT") in stub.cancelled
