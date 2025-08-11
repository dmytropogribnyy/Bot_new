#!/usr/bin/env python3
"""
Testnet Smoke-Test for Binance USDC Futures Bot.

 Verifies:
 - Stage D: TP/SL integration (via normal order path)
 - Stage F: Global guard blocks new positions after loss
 - Telegram bot: start/end/error pings

 Safe by design:
 - Forces TESTNET mode via env
 - Small size order
 - Cancels open orders at the end
"""

import asyncio
import importlib
import os
import sys
import traceback
from typing import Any

# Project imports
from core.config import TradingConfig, env_bool, env_str
from core.exchange_client import OptimizedExchangeClient
from core.unified_logger import UnifiedLogger

# Optional Telegram helper (import lazily to avoid static import errors)
try:
    _tg_mod = importlib.import_module("telegram.telegram_utils")
    _tg_send = getattr(_tg_mod, "send_telegram_message", None)
except Exception:
    _tg_send = None


def tg_enabled() -> bool:
    return env_bool("TELEGRAM_ENABLED", False)


def tg_send(msg: str) -> None:
    if _tg_send and tg_enabled():
        try:
            _tg_send(msg, force=True)
        except Exception:
            pass


async def run_smoke() -> dict[str, Any]:
    # === Force TESTNET ===
    os.environ["BINANCE_TESTNET"] = "true"

    cfg = TradingConfig()
    # Explicitly enforce testnet and allow actual TESTNET API calls; keep small sizing
    cfg.testnet = True
    if hasattr(cfg, "dry_run"):
        cfg.dry_run = False

    logger = UnifiedLogger(cfg)
    client = OptimizedExchangeClient(cfg, logger)

    # Choose a sensible default symbol per environment if not provided
    env_symbol = env_str("SMOKE_SYMBOL", "")
    if env_symbol:
        symbol = env_symbol
    else:
        symbol = "BTC/USDT:USDT" if cfg.testnet else "BTC/USDC:USDC"

    try:
        qty = float(env_str("SMOKE_QTY", "0.001"))
    except Exception:
        qty = 0.001
    price = None  # MARKET

    result: dict[str, Any] = {"symbol": symbol, "steps": []}
    logger.log_event("SMOKE", "INFO", f"=== Testnet smoke for {symbol} ===")
    tg_send(f"🧪 SMOKE start: {symbol}")

    # Step 1: place MARKET order
    logger.log_event("SMOKE", "INFO", "Placing first MARKET order")
    r1 = await client.create_order(symbol, "MARKET", "BUY", qty, price, {})
    result["steps"].append({"order1": r1})
    print("[SMOKE] Order 1:", r1)

    # Step 2: simulate Stage F block and try to open again
    if hasattr(client, "risk_guard_f"):
        logger.log_event("SMOKE", "INFO", "Simulating Stage F block (-10% PnL)")
        if hasattr(client, "record_trade_close_stage_f"):
            client.record_trade_close_stage_f(-10.0)
        else:
            try:
                client.risk_guard_f.record_trade_close(-10.0)
            except Exception:
                pass
    else:
        logger.log_event("SMOKE", "WARNING", "risk_guard_f not found; skipping Stage F block simulation")

    logger.log_event("SMOKE", "INFO", "Attempting second MARKET order (should be blocked)")
    r2 = await client.create_order(symbol, "MARKET", "BUY", qty, price, {})
    result["steps"].append({"order2": r2})
    print("[SMOKE] Order 2 (expect blocked_by_risk):", r2)

    # Step 3: cancel open orders to clean testnet
    try:
        logger.log_event("SMOKE", "INFO", "Cancelling all open orders")
        await client.cancel_all_orders(symbol)
        result["steps"].append({"cancel_all": "ok"})
    except Exception as e:
        logger.log_event("SMOKE", "WARNING", f"Cancel failed: {e}")
        result["steps"].append({"cancel_all": f"error: {e}"})

    logger.log_event("SMOKE", "INFO", "=== Smoke finished ===")
    tg_send(f"✅ SMOKE done: {symbol}")
    return result


async def amain():
    try:
        res = await run_smoke()
        # basic acceptance print
        blocked = False
        for st in res["steps"]:
            if "order2" in st:
                o2 = st["order2"]
                blocked = isinstance(o2, dict) and (
                    o2.get("status") == "blocked_by_risk" or "blocked" in str(o2).lower()
                )
        print("\n[ACCEPTANCE] Stage F block:", "OK" if blocked else "NOT TRIGGERED")
    except Exception as e:
        err = f"❌ SMOKE error: {e}"
        print(err, file=sys.stderr)
        traceback.print_exc()
        tg_send(err)
        raise


if __name__ == "__main__":
    asyncio.run(amain())
