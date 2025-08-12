import json
import os
from collections import Counter
from datetime import datetime, timezone

from utils_core import extract_symbol
from core.unified_logger import UnifiedLogger

_ULOG = UnifiedLogger()


def log(message: str, level: str = "INFO") -> None:
    _ULOG.log_event("DEBUG_TOOLS", level, message)


OUTPUT_FILE = "data/debug_monitoring_summary.json"
SYMBOLS_FILE = "data/valid_usdc_symbols.json"
TUNING_LOG_FILE = "data/filter_tuning_log.json"


def scan_symbol(symbol: str, timeframe="5m", limit=100):
    import pandas as pd
    from common.leverage_config import get_leverage_for_symbol

    from core.legacy.binance_api import fetch_ohlcv
    from core.legacy.fail_stats_tracker import get_symbol_risk_factor
    from core.legacy.signal_utils import add_indicators, get_signal_breakdown, passes_1plus1
    from core.legacy.trade_engine import calculate_position_size, calculate_risk_amount
    from utils_core import get_cached_balance, get_runtime_config
    from utils_logging import log

    try:
        raw = fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw or len(raw) < 2:
            return {"status": "no_data"}

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = add_indicators(df)

        if df is None or not isinstance(df, pd.DataFrame) or df.empty or "close" not in df.columns:
            raise ValueError(
                f"[scan_symbol] Invalid df after add_indicators → type={type(df)}, columns={getattr(df, 'columns', [])}"
            )

        latest = df.iloc[-1]

        config = get_runtime_config()
        min_atr_pct = config.get("atr_threshold_percent", 0.001)
        min_volume = config.get("volume_threshold_usdc", 500)
        min_rsi = config.get("min_rsi", 25)
        max_rsi = config.get("max_rsi", 75)

        atr_percent = latest.get("atr_percent", 0)
        volume = latest.get("volume", 0)
        rsi = latest.get("rsi", 50)

        reasons = []
        if atr_percent < min_atr_pct:
            reasons.append("low_atr")
        if volume < min_volume:
            reasons.append("low_volume")
        if not (min_rsi <= rsi <= max_rsi):
            reasons.append("rsi_out_of_range")

        _, breakdown = get_signal_breakdown(df)
        passes_combo = passes_1plus1(breakdown) if breakdown else False
        r_factor, _ = get_symbol_risk_factor(symbol)

        entry_price = latest.get("close", 0)
        balance = get_cached_balance()
        leverage = get_leverage_for_symbol(symbol)

        risk_amount, effective_sl = calculate_risk_amount(
            balance, symbol=symbol, atr_percent=atr_percent, volume_usdc=volume
        )

        qty, _ = calculate_position_size(symbol, entry_price, balance, leverage)

        if not isinstance(qty, float | int) or qty <= 0:
            log(f"[SKIPPED] {symbol}: position blocked or too small (qty={qty})", level="WARNING")
            return {
                "symbol": symbol,
                "atr_pct": round(atr_percent, 5),
                "volume": round(volume, 1),
                "rsi": round(rsi, 2),
                "risk_factor": round(r_factor, 3),
                "passes_1plus1": passes_combo,
                "entry_notional": 0.0,
                "filtered": True,
                "reasons": reasons + ["qty_blocked"],
                "status": "skipped",
            }

        notional = round(qty * entry_price, 2)

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
            "status": "ok",
        }

        log(f"[debug_monitor] Scanned {symbol} result: {result}", level="DEBUG")
        return result

    except Exception as e:
        log(f"[debug_monitor] Error scanning {symbol}: {e}", level="ERROR")
        return {"status": "error", "error": str(e)}


def run_monitor():
    log("[debug_monitor] STARTED", level="WARNING")
    try:
        with open(SYMBOLS_FILE, encoding="utf-8") as f:
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

        # === Защита от некорректных форматов ===
        if not isinstance(result, dict):
            log(f"[debug_monitor] ❌ Invalid result format for {symbol}: {type(result)} → {result}", level="ERROR")
            result = {"status": "error", "error": "Invalid return from scan_symbol"}

        summary[symbol] = result

        status = result.get("status")
        if status == "no_data":
            print("⚠️ no data")
        elif status == "error":
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbols_count": total,
        "results": summary,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # === Write tuning log ===
    reason_counts = dict(Counter(filter_reasons))
    tuning_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_symbols": total,
        "filtered_symbols": filtered_count,
        "passed_symbols": total - filtered_count,
        "reasons": reason_counts,
    }
    try:
        if os.path.exists(TUNING_LOG_FILE):
            with open(TUNING_LOG_FILE, encoding="utf-8") as f:
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
