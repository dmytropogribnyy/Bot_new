import json
import os
from collections import Counter
from datetime import datetime

import pandas as pd

from core.binance_api import fetch_ohlcv
from core.fail_stats_tracker import get_symbol_risk_factor
from core.signal_utils import add_indicators, get_signal_breakdown, passes_1plus1
from core.trade_engine import calculate_position_size
from utils_core import extract_symbol, get_cached_balance
from utils_logging import log

OUTPUT_FILE = "data/debug_monitoring_summary.json"
SYMBOLS_FILE = "data/valid_usdc_symbols.json"
TUNING_LOG_FILE = "data/filter_tuning_log.json"

MIN_ATR_PCT = 0.003
MIN_VOLUME = 1000
MIN_RSI = 30
MAX_RSI = 70


def scan_symbol(symbol: str, timeframe="5m", limit=100):
    try:
        raw = fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw or len(raw) < 2:
            return {"status": "no_data"}

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = add_indicators(df)
        latest = df.iloc[-1]

        atr_percent = latest.get("atr_percent", 0)
        volume = latest.get("volume", 0)
        rsi = latest.get("rsi", 50)

        reasons = []
        if atr_percent < MIN_ATR_PCT:
            reasons.append("low_atr")
        if volume < MIN_VOLUME:
            reasons.append("low_volume")
        if not (MIN_RSI <= rsi <= MAX_RSI):
            reasons.append("rsi_out_of_range")

        breakdown = get_signal_breakdown(df)
        passes_combo = passes_1plus1(breakdown) if breakdown else False
        r_factor, _ = get_symbol_risk_factor(symbol)

        entry_price = latest.get("close", 0)
        stop_price = entry_price * 0.99
        balance = get_cached_balance()
        qty = calculate_position_size(entry_price, stop_price, balance * 0.01, symbol=symbol)
        notional = round(qty * entry_price, 2) if qty else 0.0

        result = {
            "symbol": symbol,
            "atr_pct": round(atr_percent, 5),
            "volume": round(volume, 1),
            "rsi": round(rsi, 2),
            "risk_factor": round(r_factor, 3),
            "passes_1plus1": passes_combo,
            "entry_notional": notional,
            "filtered": bool(reasons),
            "reasons": reasons,
        }

        log(f"[debug_monitor] Scanned {symbol} result: {result}", level="DEBUG")
        return result

    except Exception as e:
        log(f"[debug_monitor] Error scanning {symbol}: {e}", level="ERROR")
        return {"status": "error", "error": str(e)}


def run_monitor():
    log("[debug_monitor] STARTED", level="WARNING")
    try:
        with open(SYMBOLS_FILE, "r", encoding="utf-8") as f:
            symbols = json.load(f)
    except Exception as e:
        log(f"[debug_monitor] Failed to load symbols file: {e}", level="ERROR")
        return

    summary = {}
    total = len(symbols)
    filtered_count = 0
    filter_reasons = []

    print(f"\n✅ Found {total} symbols\n")

    for i, item in enumerate(symbols, start=1):
        symbol = extract_symbol(item)

        print(f"[{i}/{total}] Scanning {symbol} ...", end=" ")
        result = scan_symbol(symbol)
        summary[symbol] = result

        if result.get("status") == "no_data":
            print("⚠️ no data")
        elif result.get("status") == "error":
            print("❌ error")
        elif result.get("filtered"):
            reasons = result.get("reasons", [])
            filter_reasons.extend(reasons)
            filtered_count += 1
            print(f"❌ filtered ({', '.join(reasons)})")
        else:
            print("✅ ok")

    os.makedirs("data", exist_ok=True)
    summary_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbols_count": total,
        "results": summary,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # === Write tuning log ===
    reason_counts = dict(Counter(filter_reasons))
    tuning_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_symbols": total,
        "filtered_symbols": filtered_count,
        "passed_symbols": total - filtered_count,
        "reasons": reason_counts,
    }
    try:
        if os.path.exists(TUNING_LOG_FILE):
            with open(TUNING_LOG_FILE, "r", encoding="utf-8") as f:
                log_data = json.load(f)
                if not isinstance(log_data, list):
                    log_data = []
        else:
            log_data = []
        log_data.append(tuning_entry)
        log_data = log_data[-100:]
        with open(TUNING_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        log("[debug_monitor] Tuning summary updated.", level="INFO")
    except Exception as e:
        log(f"[debug_monitor] Failed to write tuning log: {e}", level="ERROR")

    log(f"[debug_monitor] Scan complete. Saved to {OUTPUT_FILE}", level="INFO")


if __name__ == "__main__":
    run_monitor()
