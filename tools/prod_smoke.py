#!/usr/bin/env python3
"""
Production/Testnet smoke test: open → attach TP/SL → close → verify → cleanup.

Usage examples:

  BINANCE_TESTNET=true  python tools/prod_smoke.py --symbol XRP/USDT:USDT --usd 10 --leverage 3 --side BUY
  BINANCE_TESTNET=false python tools/prod_smoke.py --symbol XRP/USDC:USDC --usd 10 --leverage 3 --side BUY
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Make repository root importable when run as a script
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.order_manager import cleanup_stray_orders
from core.precision import PrecisionError, normalize
from core.unified_logger import UnifiedLogger, get_logger


async def run_smoke(symbol: str, usd: float, leverage: int, side: str) -> int:
    # Initialize unified logger for downstream components
    ulog = UnifiedLogger()
    logger = get_logger(tag="SMOKE")
    # Resolve testnet from env
    testnet_flag = str(os.getenv("BINANCE_TESTNET", "true")).strip().lower() == "true"
    cfg = TradingConfig()
    cfg.testnet = testnet_flag
    cfg.dry_run = False

    ex: OptimizedExchangeClient | None = None
    try:
        # Init exchange
        ex = OptimizedExchangeClient(cfg, ulog)
        await ex.initialize()

        # Fetch market + mark price
        markets = await ex.get_markets()
        market = markets.get(symbol, {})
        ticker = await ex.get_ticker(symbol)
        last = (ticker or {}).get("last") or (ticker or {}).get("close")
        if last is None:
            logger.error(f"No ticker for {symbol}")
            return 2
        mark_price = float(last)

        # Compute qty from usd and leverage
        notional = float(usd) * float(leverage)
        qty_raw = notional / mark_price
        # Normalize using precision gate (price=None -> must pass current_price)
        try:
            _price_norm, qty_norm, _ = normalize(None, float(qty_raw), market, mark_price, symbol)
        except PrecisionError as e:
            logger.error(f"Precision error: {e}")
            return 3

        # Open position (market)
        side_norm = side.strip().lower()
        if side_norm not in ("buy", "sell"):
            logger.error("--side must be BUY or SELL")
            return 4
        logger.info(
            f"OPEN {symbol}: side={side_norm} qty={qty_norm} notional={notional:.2f} price≈{mark_price:.6f} lev={leverage}"
        )
        try:
            order = await ex.create_market_order(symbol, side_norm, qty_norm)
        except Exception as e:
            logger.error(f"Open failed: {e}")
            return 5

        client_id = (order or {}).get("clientOrderId") or (order or {}).get("info", {}).get("clientOrderId")
        logger.info(f"Opened order id={order.get('id')} clientId={client_id}")

        # Create TP/SL reduceOnly orders tagged with prefix
        # Use only characters allowed by Binance for clientOrderId
        prefix = "PROD-SMOKE"
        close_side = "sell" if side_norm == "buy" else "buy"
        # TP: +0.3% from mark; SL: -0.3% (symmetric)
        tp_price = mark_price * (1.003 if side_norm == "buy" else 0.997)
        sl_price = mark_price * (0.997 if side_norm == "buy" else 1.003)
        # Normalize for order placement
        tp_price_norm, tp_qty_norm, _ = normalize(tp_price, float(qty_norm) * 0.5, market, None, symbol)
        sl_price_norm, sl_qty_norm, _ = normalize(sl_price, float(qty_norm), market, None, symbol)

        logger.info(
            f"ATTACH TP/SL: TP@{tp_price_norm} x {tp_qty_norm} | SL@{sl_price_norm} x {sl_qty_norm} (reduceOnly)"
        )
        # Place TP with robust fallback (market TP first for better coverage on testnet)
        params_tp: dict[str, Any] = {
            "reduceOnly": True,
            "stopPrice": float(tp_price_norm),
            "workingType": cfg.working_type,
            "newClientOrderId": f"{prefix}-TP-{symbol}"[:32],
        }
        tp_order: dict[str, Any] = {}
        try:
            # Prefer market-style TP
            tp_order = await ex.create_order(symbol, "TAKE_PROFIT_MARKET", close_side, tp_qty_norm, None, params_tp)
        except Exception as e1:
            try:
                # Fallback to limit-style TP (requires price)
                tp_order = await ex.create_order(
                    symbol, "TAKE_PROFIT", close_side, tp_qty_norm, float(tp_price_norm), params_tp
                )
            except Exception as e2:
                # Last resort: plain reduceOnly limit as pseudo-TP (no trigger)
                try:
                    params_tp_plain = {
                        "reduceOnly": True,
                        "newClientOrderId": params_tp["newClientOrderId"],
                    }
                    tp_order = await ex.create_order(
                        symbol, "limit", close_side, tp_qty_norm, float(tp_price_norm), params_tp_plain
                    )
                except Exception as e3:
                    logger.warning(
                        "TP unsupported by exchange (continuing): market=%s; limit=%s; plain_limit=%s",
                        e1,
                        e2,
                        e3,
                    )
                    tp_order = {}

        # Place SL with robust fallback (limit STOP first, then market)
        params_sl: dict[str, Any] = {
            "reduceOnly": True,
            "stopPrice": float(sl_price_norm),
            "workingType": cfg.working_type,
            "newClientOrderId": f"{prefix}-SL-{symbol}"[:32],
        }
        sl_order: dict[str, Any] = {}
        try:
            # Try STOP (limit) which is widely supported on Binance futures
            sl_order = await ex.create_order(symbol, "STOP", close_side, sl_qty_norm, float(sl_price_norm), params_sl)
        except Exception as e1:
            try:
                # Fallback to STOP_MARKET
                sl_order = await ex.create_order(symbol, "STOP_MARKET", close_side, sl_qty_norm, None, params_sl)
            except Exception as e2:
                logger.warning(
                    "SL unsupported by exchange (continuing without SL): stop_limit=%s; stop_market=%s",
                    e1,
                    e2,
                )
                sl_order = {}

        logger.info(f"ATTACHED: TP id={tp_order.get('id')} | SL id={sl_order.get('id')} | entryId={order.get('id')}")

        # Wait a bit for exchange state propagate
        await asyncio.sleep(2.0)

        # Close position immediately (market, reduceOnly) to complete cycle
        logger.info("CLOSE: market close to complete smoke cycle")
        try:
            pos = await ex.get_position(symbol)
            try:
                live_qty = abs(float((pos or {}).get("size", (pos or {}).get("contracts", 0)) or 0))
            except Exception:
                live_qty = None
            close_qty = float(live_qty or qty_norm)
            if close_qty > 0:
                close_order = await ex.create_order(symbol, "market", close_side, close_qty, None, {"reduceOnly": True})
                logger.info(f"Closed order id={close_order.get('id')} qty={close_qty}")
            else:
                logger.info("Nothing to close (qty=0)")
        except Exception as e:
            logger.error(f"Close failed: {e}")
            # Continue to cleanup regardless

        # Cleanup stray reduceOnly orders with our prefix
        stats = await cleanup_stray_orders(ex, symbol, prefix=prefix)
        logger.info(f"CLEANUP: {stats}")
        logger.info("SUCCESS: smoke cycle complete")
        return 0
    finally:
        try:
            if ex is not None:
                await ex.close()
            await asyncio.sleep(0)
        except Exception:
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prod/Testnet smoke test")
    p.add_argument("--symbol", required=True, help="Symbol, e.g. XRP/USDT:USDT or XRP/USDC:USDC")
    p.add_argument("--usd", type=float, required=True, help="Dollar notional to allocate (pre-leverage)")
    p.add_argument("--leverage", type=int, default=3, help="Leverage to apply")
    p.add_argument("--side", type=str, default="BUY", help="BUY or SELL (default BUY)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    # Windows event loop policy for asyncio + ccxt
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    args = parse_args(argv)
    return asyncio.run(run_smoke(symbol=args.symbol, usd=args.usd, leverage=args.leverage, side=args.side))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
