import json
import os
from datetime import datetime

from core.binance_api import fetch_ohlcv
from core.signal_utils import add_indicators
from utils_core import extract_symbol
from utils_logging import log

OUTPUT_FILE = "data/debug_monitoring_summary.json"
SYMBOLS_FILE = "data/valid_usdc_symbols.json"

MIN_ATR_PCT = 0.003
MIN_VOLUME = 1000
MIN_RSI = 30
MAX_RSI = 70


def scan_symbol(symbol: str, timeframe="5m", limit=100):
    try:
        df = fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not df or len(df) < 2:
            return {"status": "no_data"}

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

        return {
            "symbol": symbol,
            "atr_pct": round(atr_percent, 5),
            "volume": round(volume, 1),
            "rsi": round(rsi, 2),
            "filtered": bool(reasons),
            "reasons": reasons,
        }

    except Exception as e:
        log(f"[debug_monitor] Error scanning {symbol}: {e}", level="ERROR")
        return {"status": "error", "error": str(e)}


def run_monitor():
    try:
        with open(SYMBOLS_FILE, "r", encoding="utf-8") as f:
            symbols = json.load(f)
    except Exception as e:
        log(f"[debug_monitor] Failed to load symbols file: {e}", level="ERROR")
        return

    summary = {}
    total = len(symbols)
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
            reasons = ", ".join(result.get("reasons", []))
            print(f"❌ filtered ({reasons})")
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

    log(f"[debug_monitor] Scan complete. Saved to {OUTPUT_FILE}", level="INFO")


if __name__ == "__main__":
    run_monitor()
