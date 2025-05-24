import json
import os
from datetime import datetime

from constants import INACTIVE_CANDIDATES_FILE, SYMBOLS_FILE
from pair_selector import fetch_all_symbols, fetch_symbol_data, get_performance_score
from utils_core import get_runtime_config, load_json_file
from utils_logging import log


def continuous_scan():
    """Scan with progressively relaxed thresholds including ATR."""
    runtime_config = get_runtime_config()
    base_volume = runtime_config.get("volume_threshold_usdc", 300)
    base_score = runtime_config.get("min_perf_score", 0.15)
    base_atr = runtime_config.get("atr_threshold_percent", 0.006)
    min_candidates = runtime_config.get("scanner_min_candidates", 5)

    relaxation_stages = [
        {"name": "Standard", "volume_factor": 1.0, "score_factor": 1.0, "atr_factor": 1.0},
        {"name": "Moderate", "volume_factor": 0.7, "score_factor": 0.8, "atr_factor": 0.9},
        {"name": "Relaxed", "volume_factor": 0.5, "score_factor": 0.6, "atr_factor": 0.8},
        {"name": "Minimum", "volume_factor": 0.3, "score_factor": 0.4, "atr_factor": 0.6},
    ]

    all_symbols = set(fetch_all_symbols())
    active_symbols = set(load_json_file(SYMBOLS_FILE) or [])
    candidates = all_symbols - active_symbols

    log(f"🔍 Scanning {len(candidates)} inactive symbols across adaptive thresholds...", level="INFO")

    scan_results = []
    final_stage = relaxation_stages[0]

    for stage in relaxation_stages:
        min_volume = base_volume * stage["volume_factor"]
        min_score = base_score * stage["score_factor"]
        min_atr = base_atr * stage["atr_factor"]
        stage_results = []

        log(f"[Scan] {stage['name']} thresholds → " f"Volume ≥ {min_volume:.1f}, Score ≥ {min_score:.3f}, ATR ≥ {min_atr:.4f}", level="DEBUG")

        for symbol in sorted(candidates):
            df = fetch_symbol_data(symbol, timeframe="15m", limit=100)
            if df is None or len(df) < 20:
                continue

            price = df["close"].iloc[-1]
            if "atr" not in df.columns:
                continue  # нужно, чтобы df["atr"] был рассчитан (fetch_symbol_data может понадобиться доработать)

            atr = df["atr"].iloc[-1]
            if price == 0 or atr is None:
                continue

            volume = df["volume"].mean()
            volume_usdc = volume * price
            atr_percent = atr / price
            perf_score = get_performance_score(symbol)

            if volume_usdc >= min_volume and perf_score >= min_score and atr_percent >= min_atr:
                result = {
                    "symbol": symbol,
                    "volume_usdc": round(volume_usdc, 2),
                    "perf_score": round(perf_score, 3),
                    "atr_percent": round(atr_percent * 100, 2),
                    "last_price": round(price, 4),
                    "stage": stage["name"],
                    "timestamp": datetime.utcnow().isoformat(),
                }
                stage_results.append(result)
            else:
                log(f"[Scan] Skipped {symbol} — " f"vol={volume_usdc:.1f}, score={perf_score:.3f}, atr%={atr_percent:.4f}", level="DEBUG")

        scan_results.extend(stage_results)

        # Если уже набрали нужное кол-во кандидатов — выходим
        if len(scan_results) >= min_candidates:
            final_stage = stage
            break

    # Сортируем по perf_score и пишем в файл
    scan_results.sort(key=lambda x: x["perf_score"], reverse=True)
    os.makedirs(os.path.dirname(INACTIVE_CANDIDATES_FILE), exist_ok=True)
    with open(INACTIVE_CANDIDATES_FILE, "w") as f:
        json.dump(scan_results, f, indent=2)

    log(f"✅ Scan complete: Found {len(scan_results)} candidates using {final_stage['name']} thresholds", level="INFO")


def schedule_continuous_scanner():
    try:
        from schedule import every

        every(2).hours.do(continuous_scan)
        log("[Scheduler] continuous_scan scheduled every 2 hours", level="INFO")
    except Exception as e:
        log(f"[Scheduler] Failed to schedule continuous_scan: {e}", level="ERROR")


if __name__ == "__main__":
    continuous_scan()
