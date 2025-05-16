import json
import os
from datetime import datetime, timedelta
from threading import Lock

from constants import CACHE_FILE
from pair_selector import calculate_atr_volatility, calculate_short_term_metrics, fetch_symbol_data
from utils_logging import log

CACHE_LOCK = Lock()
MAX_ENTRIES = 1000


def add_missed_opportunity(symbol: str):
    df = fetch_symbol_data(symbol, timeframe="15m", limit=96)
    if df is None or len(df) < 20:
        return

    price_24h_ago = df["close"].iloc[0]
    price_now = df["close"].iloc[-1]
    potential_profit = ((price_now - price_24h_ago) / price_24h_ago) * 100

    if abs(potential_profit) < 5:
        return

    metrics = calculate_short_term_metrics(df)
    atr_vol = calculate_atr_volatility(df)
    avg_volume = df["volume"].mean()
    now = datetime.utcnow().isoformat()

    entry = {
        "symbol": symbol,
        "timestamp": now,
        "profit": round(potential_profit, 2),
        "momentum": round(metrics.get("momentum", 0), 2),
        "atr_vol": round(atr_vol, 4),
        "avg_volume": round(avg_volume),
    }

    with CACHE_LOCK:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        else:
            cache = []

        cache.append(entry)
        cache = cache[-MAX_ENTRIES:]  # Ограничим размер

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)


def flush_best_missed_opportunities(top_n=5):
    with CACHE_LOCK:
        if not os.path.exists(CACHE_FILE):
            return

        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        # Отбор только свежих (за последние 30 мин)
        now = datetime.utcnow()
        threshold_time = now - timedelta(minutes=30)

        recent = [entry for entry in cache if datetime.fromisoformat(entry["timestamp"]) > threshold_time]

        if not recent:
            return

        top = sorted(recent, key=lambda x: abs(x["profit"]), reverse=True)[:top_n]

        lines = [f"- {e['symbol']} ({e['profit']}% profit, Momentum: {e['momentum']}%, ATR vol: {e['atr_vol']}, Avg volume: {e['avg_volume']:,})" for e in top]
        log("[Top Missed Opportunities — Last 30 min]\n" + "\n".join(lines), level="INFO")

        # Очистим кэш после логирования
        with open(CACHE_FILE, "w") as f:
            json.dump([], f)
