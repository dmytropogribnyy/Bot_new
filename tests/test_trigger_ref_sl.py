import pytest


class _BinanceOrderWouldTrigger(Exception):
    def __init__(self, msg='binance {"code":-2021,"msg":"Order would immediately trigger."}'):
        super().__init__(msg)
        self.code = -2021


@pytest.mark.asyncio
async def test_sl_uses_mark_and_recovers_on_retry(monkeypatch):
    from core.order_manager import OrderManager
    from core.exchange_client import OptimizedExchangeClient
    from core.unified_logger import UnifiedLogger
    from core.config import TradingConfig

    cfg = TradingConfig().from_env()
    cfg.working_type = "MARK_PRICE"
    cfg.stop_loss_percent = 0.8

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

    ex.get_markets = fake_get_markets  # type: ignore[assignment]

    entry = 118_771.9
    qty = 0.003

    marks = [118_755.8, 118_755.5]
    lasts = [118_771.9, 118_771.9]
    state = {"i": 0}

    async def fake_get_ticker(symbol):
        i = state["i"]
        return {"info": {"markPrice": str(marks[i])}, "last": lasts[i], "markPrice": str(marks[i])}

    ex.get_ticker = fake_get_ticker  # type: ignore[assignment]

    placed = {"calls": [], "ok": []}

    async def fake_create_order(symbol, order_type, side, amount, price, params):
        placed["calls"].append((symbol, order_type, side, amount, price, params))
        # First SL attempt fails with -2021
        is_sl = str(order_type).upper() in {"STOP", "STOP_MARKET"}
        if is_sl and state["i"] == 0:
            state["i"] = 1
            raise _BinanceOrderWouldTrigger()
        placed["ok"].append((symbol, order_type, side, amount, price, params))
        return {"id": "ok", "type": order_type, "params": params}

    ex.create_order = fake_create_order  # type: ignore[assignment]

    await om.place_protective_orders("BTC/USDT:USDT", side="buy", entry_price=entry, quantity=qty, actual_filled=qty)

    ok = [c for c in placed["ok"] if c[1] in ("STOP", "STOP_MARKET")]
    assert ok, "SL was not placed after retry"
    _, _, _, _, _, params = ok[-1]
    assert params.get("workingType") == "MARK_PRICE"
    # Stop price must be at least 2 ticks below latest mark
    stop_price = float(params.get("stopPrice"))
    assert stop_price <= marks[1] - 2 * tick


@pytest.mark.asyncio
async def test_sl_uses_contract_price_when_configured(monkeypatch):
    from core.order_manager import OrderManager
    from core.exchange_client import OptimizedExchangeClient
    from core.unified_logger import UnifiedLogger
    from core.config import TradingConfig

    cfg = TradingConfig().from_env()
    cfg.working_type = "CONTRACT_PRICE"
    cfg.stop_loss_percent = 0.8

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

    ex.get_markets = fake_get_markets  # type: ignore[assignment]

    entry = 100.0
    qty = 0.01
    lasts = [100.0, 99.9]
    marks = [100.0, 100.0]
    state = {"i": 0}

    async def fake_get_ticker(symbol):
        i = state["i"]
        return {"info": {"markPrice": str(marks[i])}, "last": lasts[i], "markPrice": str(marks[i])}

    ex.get_ticker = fake_get_ticker  # type: ignore[assignment]

    placed = {"ok": []}

    async def fake_create_order(symbol, order_type, side, amount, price, params):
        is_sl = str(order_type).upper() in {"STOP", "STOP_MARKET"}
        if is_sl and state["i"] == 0:
            state["i"] = 1
            raise _BinanceOrderWouldTrigger()
        placed["ok"].append((symbol, order_type, side, amount, price, params))
        return {"id": "ok", "type": order_type, "params": params}

    ex.create_order = fake_create_order  # type: ignore[assignment]

    await om.place_protective_orders("BTC/USDT:USDT", side="buy", entry_price=entry, quantity=qty, actual_filled=qty)

    ok = [c for c in placed["ok"] if c[1] in ("STOP", "STOP_MARKET")]
    assert ok, "SL was not placed for CONTRACT_PRICE"
    _, _, _, _, _, params = ok[-1]
    assert params.get("workingType") in ("CONTRACT_PRICE", "LAST_PRICE")
    stop_price = float(params.get("stopPrice"))
    assert stop_price <= lasts[1] - 2 * tick
