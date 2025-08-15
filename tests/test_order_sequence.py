import pytest


@pytest.mark.asyncio
async def test_sequence_sl_then_tps(monkeypatch):
    from core.order_manager import OrderManager
    from core.exchange_client import OptimizedExchangeClient
    from core.unified_logger import UnifiedLogger
    from core.config import TradingConfig

    cfg = TradingConfig().from_env()
    cfg.working_type = "MARK_PRICE"
    cfg.enable_multiple_tp = True
    # two TP levels
    cfg.tp_levels_raw = [{"percent": 1.0, "size": 0.5}, {"percent": 2.0, "size": 0.5}]

    logger = UnifiedLogger(cfg)
    ex = OptimizedExchangeClient(cfg, logger)
    om = OrderManager(cfg, ex, logger)

    tick, step, min_qty = 0.1, 0.001, 0.002

    async def fake_get_markets():
        return {
            "BTC/USDT:USDT": {
                "info": {
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": str(tick)},
                        {"filterType": "LOT_SIZE", "stepSize": str(step)},
                    ]
                },
                "limits": {"amount": {"min": min_qty}},
            }
        }

    async def fake_get_ticker(_):
        return {"info": {"markPrice": "100.0"}, "last": 100.0, "markPrice": "100.0"}

    ex.get_markets = fake_get_markets  # type: ignore[assignment]
    ex.get_ticker = fake_get_ticker  # type: ignore[assignment]

    calls = []

    async def fake_create_order(symbol, order_type, side, amount, price, params):
        calls.append((order_type, params))
        return {"id": f"{order_type}_{len(calls)}", "type": order_type, "params": params}

    ex.create_order = fake_create_order  # type: ignore[assignment]

    await om.place_protective_orders("BTC/USDT:USDT", side="buy", entry_price=100.0, quantity=0.01, actual_filled=0.01)

    # Expect first SL call, then two TP calls
    assert len(calls) >= 3
    assert calls[0][0] in ("STOP", "STOP_MARKET")
    assert calls[1][0].startswith("TAKE_PROFIT")
    assert calls[2][0].startswith("TAKE_PROFIT")


@pytest.mark.asyncio
async def test_tp_cancelled_when_sl_fails(monkeypatch):
    from core.order_manager import OrderManager
    from core.exchange_client import OptimizedExchangeClient
    from core.unified_logger import UnifiedLogger
    from core.config import TradingConfig

    cfg = TradingConfig().from_env()
    cfg.working_type = "MARK_PRICE"
    cfg.enable_multiple_tp = True
    cfg.tp_levels_raw = [{"percent": 1.0, "size": 1.0}]

    logger = UnifiedLogger(cfg)
    ex = OptimizedExchangeClient(cfg, logger)
    om = OrderManager(cfg, ex, logger)

    tick, step, min_qty = 0.1, 0.001, 0.001

    async def fake_get_markets():
        return {
            "BTC/USDT:USDT": {
                "info": {
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": str(tick)},
                        {"filterType": "LOT_SIZE", "stepSize": str(step)},
                    ]
                },
                "limits": {"amount": {"min": min_qty}},
            }
        }

    async def fake_get_ticker(_):
        return {"info": {"markPrice": "100.0"}, "last": 100.0, "markPrice": "100.0"}

    ex.get_markets = fake_get_markets  # type: ignore[assignment]
    ex.get_ticker = fake_get_ticker  # type: ignore[assignment]

    calls = {"orders": [], "cancel_all": 0, "emergency": 0}

    class WouldTrigger(Exception):
        pass

    async def fake_create_order(symbol, order_type, side, amount, price, params):
        # Fail SLs only
        if order_type in ("STOP", "STOP_MARKET"):
            raise WouldTrigger("-2021 Order would immediately trigger")
        calls["orders"].append(order_type)
        return {"id": "ok"}

    async def fake_cancel_all(symbol):
        calls["cancel_all"] += 1
        return []

    async def fake_emergency(symbol):
        calls["emergency"] += 1
        return {"success": True}

    ex.create_order = fake_create_order  # type: ignore[assignment]
    ex.cancel_all_orders = fake_cancel_all  # type: ignore[assignment]
    om.close_position_emergency = fake_emergency  # type: ignore[assignment]

    res = await om.place_protective_orders(
        "BTC/USDT:USDT", side="buy", entry_price=100.0, quantity=0.01, actual_filled=0.01
    )

    # No TP should be left, and emergency close called
    assert not res.get("tp_orders")
    assert calls["cancel_all"] >= 1
    assert calls["emergency"] >= 1
