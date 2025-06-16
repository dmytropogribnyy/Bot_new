import json
import os
from datetime import datetime, timedelta
from threading import Lock

from core.strategy import fetch_data_multiframe  # обязательно импортируй, если ещё нет
from utils_core import extract_symbol
from utils_logging import log

CACHE_FILE = "data/cached_missed.json"  # Было раньше в constants
CACHE_LOCK = Lock()
MAX_ENTRIES = 1000


def add_missed_opportunity(symbol: str):
    from utils_core import get_runtime_config

    symbol = extract_symbol(symbol)
    df = fetch_data_multiframe(symbol)
    if df is None or len(df) < 20:
        return

    config = get_runtime_config()
    min_profit_threshold = config.get("min_profit_threshold", 0.06)

    price_24h_ago = df["close"].iloc[0]
    price_now = df["close"].iloc[-1]
    potential_profit = (price_now - price_24h_ago) / price_24h_ago

    if abs(potential_profit) < min_profit_threshold:
        return

    atr_vol = df["atr"].iloc[-1] if "atr" in df else 0
    avg_volume = df["volume"].iloc[-96:].mean() if len(df) >= 96 else df["volume"].mean()
    now = datetime.utcnow().isoformat()

    entry = {
        "symbol": symbol,
        "timestamp": now,
        "profit": round(potential_profit * 100, 2),  # в %
        "atr_vol": round(atr_vol, 4),
        "avg_volume": round(avg_volume),
        "price_now": round(price_now, 5),
    }

    with CACHE_LOCK:
        cache = []
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)

        cache.append(entry)
        cache = cache[-MAX_ENTRIES:]

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)


def flush_best_missed_opportunities(top_n=5):
    with CACHE_LOCK:
        if not os.path.exists(CACHE_FILE):
            return

        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        now = datetime.utcnow()
        threshold_time = now - timedelta(minutes=30)

        recent = [e for e in cache if datetime.fromisoformat(e["timestamp"]) > threshold_time]
        if not recent:
            return

        top = sorted(recent, key=lambda x: abs(x["profit"]), reverse=True)[:top_n]

        lines = [f"- {e['symbol']} ({e['profit']}% profit, ATR vol: {e['atr_vol']}, Avg volume: {e['avg_volume']:,})" for e in top]
        log("[Top Missed Opportunities — Last 30 min]\n" + "\n".join(lines), level="INFO")

        with open(CACHE_FILE, "w") as f:
            json.dump([], f)
