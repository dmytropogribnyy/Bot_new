import json
import os
from datetime import datetime

from constants import INACTIVE_CANDIDATES_FILE, SYMBOLS_FILE
from pair_selector import fetch_all_symbols, fetch_symbol_data, get_performance_score
from utils_logging import log

MIN_VOLUME_USDC = 300
MIN_PERF_SCORE = 0.15


def continuous_scan():
    """
    Background scan of all non-active USDC pairs.
    Identifies inactive but promising pairs and saves them to JSON for future recovery.
    Runs periodically via scheduler.
    """
    try:
        with open(SYMBOLS_FILE, "r") as f:
            active_symbols = set(json.load(f))
    except Exception:
        log("Could not load active symbols", level="WARNING")
        active_symbols = set()

    all_symbols = set(fetch_all_symbols())
    candidates = all_symbols - active_symbols
    scan_results = []

    log(f"🔍 Scanning {len(candidates)} inactive symbols...", level="INFO")

    for symbol in sorted(candidates):
        df = fetch_symbol_data(symbol, timeframe="15m", limit=100)
        if df is None or len(df) < 20:
            continue

        price = df["close"].iloc[-1]
        volume = df["volume"].mean()
        volume_usdc = volume * price

        perf_score = get_performance_score(symbol)

        if volume_usdc >= MIN_VOLUME_USDC and perf_score >= MIN_PERF_SCORE:
            scan_results.append(
                {"symbol": symbol, "volume_usdc": round(volume_usdc, 2), "perf_score": round(perf_score, 3), "last_price": round(price, 4), "timestamp": datetime.utcnow().isoformat()}
            )

    scan_results.sort(key=lambda x: (x["perf_score"], x["volume_usdc"]), reverse=True)

    os.makedirs(os.path.dirname(INACTIVE_CANDIDATES_FILE), exist_ok=True)
    with open(INACTIVE_CANDIDATES_FILE, "w") as f:
        json.dump(scan_results, f, indent=2)

    log(f"✅ continuous_scan complete. {len(scan_results)} candidates saved to inactive_candidates.json", level="INFO")


# 🔁 Scheduled integration block


def schedule_continuous_scanner():
    try:
        from schedule import every

        every(2).hours.do(continuous_scan)
        log("[Scheduler] continuous_scan scheduled every 2 hours", level="INFO")
    except Exception as e:
        log(f"[Scheduler] Failed to schedule continuous_scan: {e}", level="ERROR")


if __name__ == "__main__":
    continuous_scan()
