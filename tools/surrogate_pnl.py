#!/usr/bin/env python3
"""
Surrogate PnL Estimator (no private API)

- Uses public OHLCV data via OptimizedExchangeClient
- Runs ScalpingV1 on rolling window
- Simulates TP/SL hits and estimates PnL per hour

Usage:
  python tools/surrogate_pnl.py
"""

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Windows: enforce SelectorEventLoop for aiodns compatibility
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from core.config import TradingConfig
from core.exchange_client import OptimizedExchangeClient
from core.symbol_manager import SymbolManager
from core.unified_logger import UnifiedLogger
from strategies.scalping_v1 import ScalpingV1


@dataclass
class SimulationConfig:
    timeframe: str = "5m"
    limit: int = 500  # ~ 41.6h on 5m
    lookback_min_bars: int = 50
    max_hold_minutes: int = 60
    tp_percent: float = 0.015  # 1.5%
    sl_percent: float = 0.02  # 2.0%
    taker_fee_rate: float = 0.0004  # 0.04% per side
    per_trade_notional: float = 15.0
    top_symbols: int = 3


async def fetch_df(exchange: OptimizedExchangeClient, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    ohlcv = await exchange.get_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not ohlcv:
        return pd.DataFrame()
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def simulate_trade_path(
    direction: str,
    entry: float,
    highs: pd.Series,
    lows: pd.Series,
    close_last: float,
    tp_pct: float,
    sl_pct: float,
    fee_rate: float,
    notional: float,
) -> tuple[float, str]:
    """Return (pnl_usd, outcome) with fees subtracted."""
    if direction == "buy":
        tp_price = entry * (1 + tp_pct)
        sl_price = entry * (1 - sl_pct)
        # Check which hit first
        for h, l in zip(highs.values, lows.values, strict=False):
            if l <= sl_price:
                pnl_ratio = -sl_pct
                break
            if h >= tp_price:
                pnl_ratio = tp_pct
                break
        else:
            pnl_ratio = (close_last - entry) / entry
    else:
        tp_price = entry * (1 - tp_pct)
        sl_price = entry * (1 + sl_pct)
        for h, l in zip(highs.values, lows.values, strict=False):
            if h >= sl_price:
                pnl_ratio = -sl_pct
                break
            if l <= tp_price:
                pnl_ratio = tp_pct
                break
        else:
            pnl_ratio = (entry - close_last) / entry

    gross = notional * pnl_ratio
    fees = notional * fee_rate * 2  # entry + exit
    return gross - fees, ("TP" if pnl_ratio > 0 else ("SL" if pnl_ratio < 0 else "EXIT"))


async def simulate_symbol(symbol: str, df: pd.DataFrame, strategy: ScalpingV1, sim: SimulationConfig) -> dict:
    trades = 0
    tp_hits = 0
    sl_hits = 0
    pnl_total = 0.0

    # Convert max_hold to bars
    bar_minutes = int(sim.timeframe[:-1]) if sim.timeframe.endswith("m") else 5
    max_hold_bars = max(1, sim.max_hold_minutes // bar_minutes)

    for idx in range(sim.lookback_min_bars, len(df) - 2):
        window = df.iloc[: idx + 1].copy()
        direction, breakdown = await strategy.should_enter_trade(symbol, window)
        if not direction:
            continue

        entry = float(window["close"].iloc[-1])
        fwd_slice = df.iloc[idx + 1 : idx + 1 + max_hold_bars]
        if fwd_slice.empty:
            continue
        pnl_usd, outcome = simulate_trade_path(
            direction=direction,
            entry=entry,
            highs=fwd_slice["high"],
            lows=fwd_slice["low"],
            close_last=float(fwd_slice["close"].iloc[-1]),
            tp_pct=sim.tp_percent,
            sl_pct=sim.sl_percent,
            fee_rate=sim.taker_fee_rate,
            notional=sim.per_trade_notional,
        )

        trades += 1
        pnl_total += pnl_usd
        if outcome == "TP":
            tp_hits += 1
        elif outcome == "SL":
            sl_hits += 1

    hours = (len(df) * bar_minutes) / 60.0
    pnl_per_hour = pnl_total / hours if hours > 0 else 0.0
    win_rate = (tp_hits / trades * 100.0) if trades else 0.0
    return {
        "symbol": symbol,
        "trades": trades,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        "win_rate_pct": round(win_rate, 2),
        "pnl_total_usd": round(pnl_total, 2),
        "pnl_per_hour_usd": round(pnl_per_hour, 4),
        "hours": round(hours, 2),
    }


async def main():
    os.environ.setdefault("DRY_RUN", "true")
    cfg = TradingConfig()
    # Use main endpoints for richer public data
    cfg.testnet = False
    # Strategy overrides for simulation
    cfg.volume_threshold = 1.5  # volume ratio threshold
    cfg.macd_strength_override = 0.001  # easier MACD trigger
    logger = UnifiedLogger(cfg)
    exchange = OptimizedExchangeClient(cfg, logger)
    await exchange.initialize()
    symbol_manager = SymbolManager(cfg, exchange, logger)
    strategy = ScalpingV1(cfg, logger)
    sim = SimulationConfig()

    symbols = await symbol_manager.get_symbols_with_volume_filter(min_volume_usdc=200000)
    if not symbols:
        symbols = [
            "BTC/USDC:USDC",
            "ETH/USDC:USDC",
            "SOL/USDC:USDC",
        ]

    symbols = symbols[: sim.top_symbols]
    results: list[dict] = []
    for s in symbols:
        df = await fetch_df(exchange, s, sim.timeframe, sim.limit)
        if df.empty:
            continue
        res = await simulate_symbol(s, df, strategy, sim)
        results.append(res)

    # Aggregate
    total_pnl = sum(r["pnl_total_usd"] for r in results)
    total_hours = sum(r["hours"] for r in results) / max(1, len(results))  # average horizon
    pnl_per_hour = total_pnl / total_hours if total_hours > 0 else 0.0

    print("Surrogate PnL Summary (public OHLCV, simulated TP/SL):")
    for r in results:
        print(
            f"- {r['symbol']}: trades={r['trades']}, win={r['win_rate_pct']}%, "
            f"PnL_total=${r['pnl_total_usd']}, PnL/hr=${r['pnl_per_hour_usd']} (hours={r['hours']})"
        )
    print(f"\nEstimated PnL/hr (avg across symbols): ${pnl_per_hour:.3f}")

    await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())
