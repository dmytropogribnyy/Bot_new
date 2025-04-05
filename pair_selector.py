import json
import os
from datetime import datetime, timedelta

from config import (
    DRY_RUN,
    DRY_RUN_VOLATILITY_ATR_THRESHOLD,
    DRY_RUN_VOLATILITY_RANGE_THRESHOLD,
    EXPORT_PATH,
    FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS,
    MIN_DYNAMIC_PAIRS,
    TIMEZONE,
    VOLATILITY_ATR_THRESHOLD,
    VOLATILITY_RANGE_THRESHOLD,
    exchange,
)
from utils import log, send_telegram_message

SAVE_PATH = "data/dynamic_symbols.json"


def fetch_usdc_futures_symbols():
    try:
        markets = exchange.load_markets()
        usdc_futures = [
            symbol
            for symbol, data in markets.items()
            if symbol.endswith("/USDC:USDC") and data.get("swap")
        ]
        print(f"✅ USDC Perpetual Futures (swap) found: {len(usdc_futures)}")
        print("💡 Example USDC Perpetual Futures:", usdc_futures[:10])
        return usdc_futures
    except Exception as e:
        print(f"⚠️ Error loading markets: {e}")
        return []


def get_metrics(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        volume = ticker.get("quoteVolume", 0)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=24)
        prices = [c[4] for c in ohlcv if c[4] is not None]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        if not prices:
            return None
        close = prices[-1]
        atr = max([h - low for h, low in zip(highs, lows)]) / close
        day_range = (max(highs) - min(lows)) / close
        return {
            "symbol": symbol,
            "volume": volume,
            "atr_ratio": round(atr, 5),
            "range_ratio": round(day_range, 5),
        }
    except Exception as e:
        print(f"⚠️ Error fetching metrics for {symbol}: {e}")
        return None


def load_trade_stats():
    try:
        df = None
        import pandas as pd

        if os.path.exists(EXPORT_PATH):
            df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
            df = df[df["Date"] >= pd.Timestamp.now().tz_localize(TIMEZONE) - timedelta(days=3)]
        return df
    except Exception:
        return None


def get_score(metrics, history_df):
    score = 0
    atr_threshold = DRY_RUN_VOLATILITY_ATR_THRESHOLD if DRY_RUN else VOLATILITY_ATR_THRESHOLD
    range_threshold = DRY_RUN_VOLATILITY_RANGE_THRESHOLD if DRY_RUN else VOLATILITY_RANGE_THRESHOLD
    if metrics["volume"] >= 5_000_000:
        score += 1
    if metrics["atr_ratio"] >= atr_threshold:
        score += 1
    if metrics["range_ratio"] >= range_threshold:
        score += 1
    if history_df is not None:
        symbol_trades = history_df[history_df["Symbol"] == metrics["symbol"]]
        if len(symbol_trades) >= 2:
            score += 1
        if "TP2" in symbol_trades["Result"].values:
            score += 1
    return score


def select_active_symbols():
    from config import USE_DYNAMIC_IN_DRY_RUN

    if DRY_RUN and not USE_DYNAMIC_IN_DRY_RUN:
        return FIXED_PAIRS

    all_symbols = fetch_usdc_futures_symbols()
    history_df = load_trade_stats()
    evaluated = []
    log(f"Total fetched symbols: {len(all_symbols)}")
    all_symbols = list(set(all_symbols))

    for symbol in all_symbols:
        if symbol in FIXED_PAIRS:
            continue
        metrics = get_metrics(symbol)
        if not metrics:
            continue
        score = get_score(metrics, history_df)
        metrics["score"] = score
        evaluated.append(metrics)

    max_dynamic_pairs = MAX_DYNAMIC_PAIRS - len(FIXED_PAIRS)
    min_dynamic_pairs = max(0, MIN_DYNAMIC_PAIRS - len(FIXED_PAIRS))
    selected = sorted(evaluated, key=lambda x: x["score"], reverse=True)[:max_dynamic_pairs]
    log(f"Evaluated {len(evaluated)} pairs, selected {len(selected)} dynamic pairs.")

    if len(selected) < min_dynamic_pairs:
        selected = sorted(evaluated, key=lambda x: x["score"], reverse=True)[:min_dynamic_pairs]

    dynamic_symbols = [s["symbol"] for s in selected]
    active_symbols = list(set(FIXED_PAIRS + dynamic_symbols))
    skipped = [s["symbol"] for s in evaluated if s["symbol"] not in active_symbols]

    with open(SAVE_PATH, "w") as f:
        json.dump(active_symbols, f, indent=2)

    top_names = [s["symbol"].split("/")[0] for s in selected][:5]
    skipped_names = [s.split("/")[0] for s in skipped[:5]]

    msg = (
        f"✅ Pair scan complete ({datetime.now(TIMEZONE).strftime('%H:%M')})\n\n"
        f"🎯 Active today: {len(active_symbols)} pairs\n"
        f"• Fixed: {', '.join(p.split('/')[0] for p in FIXED_PAIRS)}\n"
        f"• Top dynamic: {', '.join(top_names)}\n\n"
        f"❌ Skipped (low score): {', '.join(skipped_names)}"
    )
    send_telegram_message(msg, force=True)

    return active_symbols


if __name__ == "__main__":
    select_active_symbols()
