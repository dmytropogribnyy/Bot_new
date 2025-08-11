#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

# Fix Windows event loop issue
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger


async def main():
    cfg = TradingConfig.from_env()
    logger = UnifiedLogger(cfg)

    print("=" * 50)
    print("BINANCE FUTURES BOT - SYSTEM CHECK")
    print("=" * 50)
    print(f"Mode: {'TESTNET' if cfg.testnet else 'PRODUCTION'}")
    print(f"Quote Currency: {cfg.resolved_quote_coin}")
    print(f"Leverage: {cfg.default_leverage}x")
    print(f"TP Style: {cfg.tp_order_style}")
    print(f"Working Type: {cfg.working_type}")
    print(f"Max Positions: {cfg.max_positions}")
    print(f"Stop Loss: {cfg.sl_percent}%")
    print(f"Take Profit: {cfg.take_profit_percent}%")
    print(f"WebSocket: {'Enabled' if cfg.enable_websocket else 'Disabled'}")
    print("=" * 50)

    try:
        ex = OptimizedExchangeClient(cfg, logger)
        await ex.initialize()

        # Проверка прав
        await ex.assert_futures_perms()
        print("OK - API Permissions: OK")

        # Проверка позиций
        positions = await ex.get_all_positions()
        open_pos = [p for p in positions if float(p.get("contracts", p.get("size", 0))) > 0]

        print(f"\nOPEN POSITIONS: {len(open_pos)}")
        total_margin = 0
        for p in open_pos:
            symbol = p["symbol"]
            size = float(p.get("contracts", p.get("size", 0)))
            mark = float(p.get("markPrice", 0))
            pnl = float(p.get("unrealizedPnl", 0))

            # Проверяем наличие SL
            orders = await ex.get_open_orders(symbol)
            has_sl = False
            for o in orders:
                otype = str(o.get("type") or o.get("info", {}).get("type") or "").upper()
                is_reduce = (o.get("reduceOnly") is True) or (o.get("info", {}).get("reduceOnly") is True)
                if (("STOP" in otype) or (otype in {"STOP", "STOP_MARKET"})) and is_reduce:
                    has_sl = True
                    break

            sl_status = "OK SL" if has_sl else "WARNING NO SL!"

            print(f"  {symbol}: {size} @ {mark:.4f} | PnL: ${pnl:.2f} | {sl_status}")
            total_margin += abs(size * mark / cfg.default_leverage)

        if open_pos:
            print(f"\nTotal Margin Used: ${total_margin:.2f}")

        # Проверка баланса
        balance = await ex.get_balance()
        quote_balance = balance.get(cfg.resolved_quote_coin, {})
        free = float(quote_balance.get("free", 0))
        total = float(quote_balance.get("total", 0))
        print(f"\nBALANCE {cfg.resolved_quote_coin}:")
        print(f"  Free: {free:.2f}")
        print(f"  Total: {total:.2f}")

        await ex.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1

    print("\nSystem check complete")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
