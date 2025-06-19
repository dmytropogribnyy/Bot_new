import json
import os
import threading

from utils_logging import log

CACHE_FILE = "data/cached_missed.json"
MAX_ENTRIES = 100
CACHE_LOCK = threading.Lock()


def add_missed_opportunity(symbol, entry_price, reason, breakdown):
    """
    Добавляет символ в список пропущенных возможностей.
    """
    entry = {
        "symbol": symbol,
        "entry_price": entry_price,
        "reason": reason,
        "breakdown": breakdown,
    }

    with CACHE_LOCK:
        cache = []
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                try:
                    cache = json.load(f)
                    if not isinstance(cache, list):
                        log("[MissedTracker] WARNING: Cache corrupted, resetting to empty list", level="WARNING")
                        cache = []
                except Exception as e:
                    log(f"[MissedTracker] Cache load error: {e}", level="WARNING")
                    cache = []

        cache.append(entry)
        cache = cache[-MAX_ENTRIES:]

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)


def flush_best_missed_opportunities():
    """
    Возвращает список последних пропущенных возможностей.
    Используется для отладки и анализа сигналов.
    """
    with CACHE_LOCK:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    else:
                        log("[MissedTracker] Unexpected cache format, returning empty list", level="WARNING")
                        return []
                except Exception as e:
                    log(f"[MissedTracker] Cache read error: {e}", level="WARNING")
                    return []
        return []
