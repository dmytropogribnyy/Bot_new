import json
import os
import threading
import time

from utils_logging import log

CACHE_LOCK = threading.Lock()
MAX_ENTRIES = 100
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cached_missed.json")


def ensure_missed_log_exists():
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            json.dump([], f)


def get_missed_opportunities() -> list[dict]:
    ensure_missed_log_exists()
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
            if not isinstance(cached, list):
                log("[MissedTracker] cached_missed.json is not a list. Resetting.", level="WARNING")
                return []
            return cached
    except Exception as e:
        log(f"[MissedTracker] Failed to load missed cache: {e}", level="WARNING")
        return []


def save_missed_opportunities(data: list[dict]):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data[:MAX_ENTRIES], f, indent=2)
    except Exception as e:
        log(f"[MissedTracker] Failed to save missed cache: {e}", level="ERROR")


def record_missed_opportunity(symbol: str, entry_price: float, reason: str, breakdown: dict | None = None):
    entry = {
        "symbol": symbol,
        "entry_price": round(entry_price, 6),
        "reason": reason,
        "breakdown": breakdown or {},
        "timestamp": time.time(),
    }

    with CACHE_LOCK:
        data = get_missed_opportunities()
        data.insert(0, entry)
        save_missed_opportunities(data)

    log(f"[MissedTracker] Recorded missed entry {symbol} @ {entry_price:.4f} — {reason}", level="INFO")


def flush_best_missed_opportunities(limit: int = 5) -> list[dict]:
    with CACHE_LOCK:
        data = get_missed_opportunities()
        return data[:limit]
