import asyncio
import types

import pytest

from core.utils.price_qty_utils import round_to_tick, nudge_price


@pytest.mark.asyncio
async def test_long_sl_tp_sides(order_manager, symbol):
    # Arrange
    entry = 100.0
    side = "buy"
    om = order_manager

    # Stub market schema
    async def fake_get_markets():
        return {
            symbol: {
                "info": {
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                    ]
                }
            }
        }

    async def fake_get_ticker(_s):
        return {"last": entry}

    om.exchange.get_markets = fake_get_markets  # type: ignore[assignment]
    om.exchange.get_ticker = fake_get_ticker  # type: ignore[assignment]
    # Force single TP level at 1.0% and ignore env TP_LEVELS
    om.config.enable_multiple_tp = True
    om.config.tp_levels_raw = []
    om.config.step_tp_levels = [0.01]
    om.config.step_tp_sizes = [1.0]

    # Capture created orders
    created = []

    async def fake_create_order(symbol, type, side, amount, price=None, params=None):
        created.append(
            {"symbol": symbol, "type": type, "side": side, "amount": amount, "price": price, "params": params or {}}
        )
        return {"id": f"{type}_{len(created)}", "status": "open", "symbol": symbol}

    om.exchange.create_order = fake_create_order  # type: ignore[assignment]

    # Act
    await om.place_protective_orders(symbol, side, entry, 1.0, actual_filled=1.0)

    # Assert: one SL and ≥1 TP exist and on correct side of entry
    sl = next(o for o in created if o["type"].startswith("STOP"))
    tps = [o for o in created if o["type"].startswith("TAKE_PROFIT")]
    assert sl["params"]["stopPrice"] < entry  # SL below for long
    assert all((o["params"].get("stopPrice", o.get("price")) or 0) > entry for o in tps)  # TP above for long
    # TP1 about +1%
    tp1 = tps[0]
    tp_price = tp1["params"].get("stopPrice", tp1.get("price"))
    assert abs(tp_price - 101.0) <= 0.1


@pytest.mark.asyncio
async def test_short_sl_tp_sides(order_manager, symbol):
    entry = 100.0
    side = "sell"
    om = order_manager

    async def fake_get_markets():
        return {
            symbol: {
                "info": {
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                    ]
                }
            }
        }

    async def fake_get_ticker(_s):
        return {"last": entry}

    om.exchange.get_markets = fake_get_markets  # type: ignore[assignment]
    om.exchange.get_ticker = fake_get_ticker  # type: ignore[assignment]
    # Force single TP level at 1.0% and ignore env TP_LEVELS
    om.config.enable_multiple_tp = True
    om.config.tp_levels_raw = []
    om.config.step_tp_levels = [0.01]
    om.config.step_tp_sizes = [1.0]

    created = []

    async def fake_create_order(symbol, type, side, amount, price=None, params=None):
        created.append(
            {"symbol": symbol, "type": type, "side": side, "amount": amount, "price": price, "params": params or {}}
        )
        return {"id": f"{type}_{len(created)}", "status": "open", "symbol": symbol}

    om.exchange.create_order = fake_create_order  # type: ignore[assignment]

    await om.place_protective_orders(symbol, side, entry, 1.0, actual_filled=1.0)

    sl = next(o for o in created if o["type"].startswith("STOP"))
    tps = [o for o in created if o["type"].startswith("TAKE_PROFIT")]
    assert sl["params"]["stopPrice"] > entry  # SL above for short
    assert all((o["params"].get("stopPrice", o.get("price")) or 0) < entry for o in tps)  # TP below for short


def test_nudging_correct_direction():
    tick = 0.1
    cur = 100.0
    # Long SL should be below current by ≥ 1 tick after nudging
    p = nudge_price(cur, cur, tick, side="buy", is_sl=True, min_ticks=2)
    assert p <= cur - tick


@pytest.mark.asyncio
async def test_retry_on_2021_for_sl(order_manager, symbol):
    entry = 100.0
    side = "buy"
    om = order_manager

    async def fake_get_markets():
        return {
            symbol: {
                "info": {
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                    ]
                }
            }
        }

    async def fake_get_ticker(_s):
        return {"last": entry}

    om.exchange.get_markets = fake_get_markets  # type: ignore[assignment]
    om.exchange.get_ticker = fake_get_ticker  # type: ignore[assignment]

    calls = {"n": 0}

    class FakeE(Exception):
        pass

    async def fake_create_order(symbol, type, side, amount, price=None, params=None):
        calls["n"] += 1
        if type.startswith("STOP") and calls["n"] == 1:
            raise FakeE("-2021 Filter failure")
        return {"id": f"{type}_{calls['n']}", "status": "open", "symbol": symbol}

    om.exchange.create_order = fake_create_order  # type: ignore[assignment]

    await om.place_protective_orders(symbol, side, entry, 1.0, actual_filled=1.0)
    assert calls["n"] >= 2  # retried at least once
