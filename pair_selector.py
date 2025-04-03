import os
import json
from datetime import datetime, timedelta
from config import (
    exchange, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, FIXED_PAIRS,
    MAX_DYNAMIC_PAIRS, MIN_DYNAMIC_PAIRS,
    VOLATILITY_ATR_THRESHOLD, VOLATILITY_RANGE_THRESHOLD,
    EXPORT_PATH, TIMEZONE, DRY_RUN
)
from utils import send_telegram_message

SAVE_PATH = "data/dynamic_symbols.json"

def fetch_usdc_futures_symbols():
    markets = exchange.load_markets()
    return [
        symbol for symbol, data in markets.items()
        if symbol.endswith("/USDC") and data.get("type") == "future"
    ]

def get_metrics(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        volume = ticker.get("quoteVolume", 0)

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=24)
        prices = [c[4] for c in ohlcv if c[4] is not None]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]

        if not prices:
            return None

        close = prices[-1]
        atr = max([h - l for h, l in zip(highs, lows)]) / close
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
            df = pd.read_csv(EXPORT_PATH, parse_dates=['Date'])
            df = df[df['Date'] >= pd.Timestamp.now().tz_localize(TIMEZONE) - timedelta(days=3)]
        return df
    except:
        return None

def get_score(metrics, history_df):
    score = 0
    if metrics["volume"] >= 5_000_000:
        score += 1
    if metrics["atr_ratio"] >= VOLATILITY_ATR_THRESHOLD:
        score += 1
    if metrics["range_ratio"] >= VOLATILITY_RANGE_THRESHOLD:
        score += 1
    if history_df is not None:
        symbol_trades = history_df[history_df['Symbol'] == metrics["symbol"]]
        if len(symbol_trades) >= 2:
            score += 1
        if "TP2" in symbol_trades['Result'].values:
            score += 1
    return score

def select_active_symbols():
    if DRY_RUN:
        return FIXED_PAIRS  # В режиме dry — только якорные

    all_symbols = fetch_usdc_futures_symbols()
    history_df = load_trade_stats()
    evaluated = []

    for symbol in all_symbols:
        if symbol in FIXED_PAIRS:
            continue
        metrics = get_metrics(symbol)
        if not metrics:
            continue
        score = get_score(metrics, history_df)
        metrics["score"] = score
        evaluated.append(metrics)

    # Сортируем по убыванию score
    sorted_symbols = sorted(evaluated, key=lambda x: x["score"], reverse=True)

    # Берём top-N по лимиту
    selected = sorted_symbols[:MAX_DYNAMIC_PAIRS]
    if len(selected) < MIN_DYNAMIC_PAIRS:
        selected = sorted_symbols[:MIN_DYNAMIC_PAIRS]

    active_symbols = FIXED_PAIRS + [s["symbol"] for s in selected]
    skipped = [s["symbol"] for s in evaluated if s["symbol"] not in active_symbols]

    with open(SAVE_PATH, "w") as f:
        json.dump(active_symbols, f, indent=2)

    # Telegram отчёт (только если не DRY_RUN)
    top_names = [s["symbol"].split("/")[0] for s in selected[:5]]
    skipped_names = [s.split("/")[0] for s in skipped[:5]]

    send_telegram_message(
        f"✅ Pair scan complete ({datetime.now(TIMEZONE).strftime('%H:%M')})\n\n"
        f"🎯 Active today: {len(active_symbols)} pairs\n"
        f"• Fixed: {', '.join(p.split('/')[0] for p in FIXED_PAIRS)}\n"
        f"• Top dynamic: {', '.join(top_names)}\n\n"
        f"❌ Skipped (low score): {', '.join(skipped_names)}",
        force=True
    )

    return active_symbols

if __name__ == "__main__":
    select_active_symbols()
