# continuous_scanner.py

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from constants import INACTIVE_CANDIDATES_FILE, SYMBOLS_FILE
from pair_selector import fetch_all_symbols, fetch_symbol_data
from telegram.telegram_utils import send_telegram_message
from utils_core import get_runtime_config, load_json_file
from utils_logging import log


def continuous_scan():
    """
    Сканируем «неактивные» символы и пытаемся найти кандидатов,
    фильтруя их по объёму (volume_usdc) и ATR(%), с постепенным «размягчением» порогов.
    """

    runtime_config = get_runtime_config()

    # При желании можно отменять скан в DRY_RUN
    # if runtime_config.get("DRY_RUN"):
    #     log("[continuous_scan] DRY_RUN mode => skipping scan", level="INFO")
    #     return

    base_volume = runtime_config.get("volume_threshold_usdc", 300)
    base_atr = runtime_config.get("atr_threshold_percent", 0.006)
    min_candidates = runtime_config.get("scanner_min_candidates", 5)

    # Пример динамического подхода: min_candidates = max(int(len(candidates) * 0.05), 5)
    # Но оставим константное использование min_candidates
    # all_symbols ... -> после вычислим

    # Этапы релаксации фильтров
    relaxation_stages = [
        {"name": "Standard", "volume_factor": 1.0, "atr_factor": 1.0},
        {"name": "Moderate", "volume_factor": 0.7, "atr_factor": 0.9},
        {"name": "Relaxed", "volume_factor": 0.5, "atr_factor": 0.8},
        {"name": "Minimum", "volume_factor": 0.3, "atr_factor": 0.6},
    ]

    from utils_core import normalize_symbol

    # Загружаем и нормализуем все доступные символы с биржи
    all_symbols = set(normalize_symbol(s) for s in fetch_all_symbols())
    # Загружаем и нормализуем активные символы из файла
    loaded = load_json_file(SYMBOLS_FILE) or []
    active_symbols = set(normalize_symbol(item["symbol"]) for item in loaded if isinstance(item, dict) and "symbol" in item)

    candidates = all_symbols - active_symbols

    log(f"🔍 Scanning {len(candidates)} inactive symbols with adaptive volume/ATR thresholds...", level="INFO")

    scan_results = []
    final_stage = relaxation_stages[0]

    for stage in relaxation_stages:
        min_volume = base_volume * stage["volume_factor"]
        min_atr = base_atr * stage["atr_factor"]
        stage_results = []

        log_msg = f"[Scan] {stage['name']} thresholds => " f"Volume ≥ {min_volume:.1f}, ATR% ≥ {min_atr:.4f}"
        log(log_msg, level="DEBUG")

        for symbol in sorted(candidates):
            df = fetch_symbol_data(symbol, timeframe="15m", limit=100)
            if df is None or len(df) < 20:
                # Можно логировать или просто пропускать
                continue

            # Убедимся, что 'atr' действительно в DataFrame
            if "atr" not in df.columns:
                log(f"[Scan] {symbol} => No 'atr' column in df, skipping", level="DEBUG")
                continue

            last_price = df["close"].iloc[-1]
            if not last_price or last_price == 0:
                continue

            atr_val = df["atr"].iloc[-1]
            if pd.isna(atr_val) or not np.isfinite(atr_val):
                # Глючные данные
                continue

            volume = df["volume"].mean()
            volume_usdc = volume * last_price
            atr_percent = atr_val / last_price

            # Проверяем пороги
            if volume_usdc >= min_volume and atr_percent >= min_atr:
                # Доп поля
                volatility_score = volume_usdc * atr_percent

                info = {
                    "symbol": symbol,
                    "type": "inactive",  # Помечаем, что это список "inactive"
                    "volume_stage": round(min_volume, 2),
                    "atr_stage": round(min_atr, 5),
                    "avg_volume": round(volume, 2),
                    "volume_usdc": round(volume_usdc, 2),
                    "atr_value": round(float(atr_val), 6),
                    "atr_percent": round(atr_percent * 100, 3),
                    "volatility_score": round(volatility_score, 6),
                    "last_price": round(last_price, 4),
                    "stage": stage["name"],
                    "timestamp": datetime.utcnow().isoformat(),
                }
                stage_results.append(info)
            else:
                log(f"[Scan] Skipped {symbol} => vol={volume_usdc:.1f}, atr%={atr_percent:.4f}", level="DEBUG")

        # Добавляем результаты
        scan_results.extend(stage_results)

        # Если уже набрали нужное кол-во кандидатов, завершаем
        if len(scan_results) >= min_candidates:
            final_stage = stage
            break

    # Можно сортировать по volume_usdc или volatility_score
    scan_results.sort(key=lambda x: x["volatility_score"], reverse=True)

    # Проверяем, не 0 ли
    if not scan_results:
        log("⚠️ No candidates found at any relaxation stage.", level="WARNING")
        send_telegram_message("⚠️ continuous_scan: No symbols passed filters.", force=True)

    # Сохраняем в JSON
    os.makedirs(os.path.dirname(INACTIVE_CANDIDATES_FILE), exist_ok=True)
    with open(INACTIVE_CANDIDATES_FILE, "w", encoding="utf-8") as f:
        json.dump(scan_results, f, indent=2)

    log((f"✅ Scan complete: Found {len(scan_results)} candidates " f"using {final_stage['name']} thresholds"), level="INFO")


def schedule_continuous_scanner():
    """
    Пример планировщика для continuous_scan().
    """
    try:
        from schedule import every

        every(2).hours.do(continuous_scan)
        log("[Scheduler] continuous_scan scheduled every 2 hours", level="INFO")
    except Exception as e:
        log(f"[Scheduler] Failed to schedule continuous_scan: {e}", level="ERROR")


if __name__ == "__main__":
    continuous_scan()
