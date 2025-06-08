# pair_selector.py

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Lock

import pandas as pd

from common.config_loader import (
    FIXED_PAIRS,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
    get_priority_small_balance_pairs,
)
from constants import SIGNAL_FAILURES_FILE, SYMBOLS_FILE
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from core.fail_stats_tracker import FAIL_STATS_FILE, get_symbol_risk_factor
from telegram.telegram_utils import send_telegram_message
from utils_core import (
    calculate_atr_volatility,
    extract_symbol,
    get_cached_balance,
    get_market_volatility_index,
    get_runtime_config,
    is_optimal_trading_hour,
    load_json_file,
    normalize_symbol,
    safe_call_retry,
    save_json_file,
)
from utils_logging import log  # или ваш метод логирования

BASE_UPDATE_INTERVAL = 60 * 15  # 15 минут
symbols_file_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS

_last_logged_hour = None


def auto_update_valid_pairs_if_needed():
    """
    Обновляет valid_usdc_symbols.json каждые 6 часов через test_api.py.
    """
    last_updated_path = Path("data/valid_usdc_last_updated.txt")
    now = int(time.time())

    if last_updated_path.exists():
        with last_updated_path.open("r") as f:
            last_time = int(f.read().strip())
            if now - last_time < 6 * 3600:
                return

    print("🕒 Valid USDC symbols outdated — running test_api.py")

    result = subprocess.call([sys.executable, "test_api.py"])
    if result != 0:
        log("[Updater] test_api.py failed to execute", level="ERROR")
    else:
        log("[Updater] test_api.py completed successfully", level="INFO")

    valid_file = Path("data/valid_usdc_symbols.json")
    if not valid_file.exists():
        log("⚠️ valid_usdc_symbols.json was not created!", level="ERROR")
        return

    with last_updated_path.open("w") as f:
        f.write(str(now))


def get_filter_tiers():
    """
    Multi-tier (ATR, volume) фильтры, если хочется адаптации (0.006→0.005…).
    """
    config = get_runtime_config()
    return config.get(
        "FILTER_TIERS",
        [
            {"atr": 0.006, "volume": 600},
            {"atr": 0.005, "volume": 500},
            {"atr": 0.004, "volume": 400},
            {"atr": 0.003, "volume": 300},
        ],
    )


def load_valid_usdc_symbols():
    path = Path("data/valid_usdc_symbols.json")
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    else:
        from common.config_loader import USDC_SYMBOLS

        return USDC_SYMBOLS


def load_failure_stats():
    try:
        with open(FAIL_STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_all_symbols():
    """
    Возвращает список USDC-пар из valid_usdc_symbols.json или fallback на USDC_SYMBOLS.
    """
    try:
        symbols = load_valid_usdc_symbols()
        if symbols:
            log(f"✅ Loaded {len(symbols)} symbols from valid_usdc_symbols.json", level="INFO")
            return symbols
        else:
            log("⚠️ valid_usdc_symbols.json is empty — using fallback USDC_SYMBOLS", level="WARNING")
    except Exception as e:
        log(f"⚠️ Error loading valid_usdc_symbols.json: {e}", level="ERROR")

    from common.config_loader import USDC_SYMBOLS

    return USDC_SYMBOLS


def fetch_symbol_data(symbol, timeframe="15m", limit=100):
    try:
        symbol = extract_symbol(symbol)  # 💡 ключевой шаг
        api_symbol = convert_symbol(symbol)
        ohlcv = safe_call_retry(exchange.fetch_ohlcv, api_symbol, timeframe, limit=limit, label=f"fetch_ohlcv {symbol}")
        if not ohlcv or len(ohlcv) < 10:
            log(f"No or insufficient OHLCV data for {symbol}", level="WARNING")
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def auto_cleanup_signal_failures(threshold=5000, keep_last=1000):
    """
    Если signal_failures.json разросся, подчищаем.
    """
    try:
        if os.path.exists(SIGNAL_FAILURES_FILE):
            data = load_json_file(SIGNAL_FAILURES_FILE)
            if isinstance(data, list) and len(data) > threshold:
                trimmed = data[-keep_last:]
                save_json_file(SIGNAL_FAILURES_FILE, trimmed)
                log(f"🧹 Cleaned signal_failures.json: kept last {keep_last} of {len(data)}", level="INFO")
    except Exception as e:
        log(f"⚠️ Error auto-cleaning signal_failures.json: {e}", level="ERROR")


def get_pair_limits():
    """
    min_dynamic_pairs / max_dynamic_pairs из runtime_config.json.
    """
    config = get_runtime_config()
    min_dyn = config.get("min_dynamic_pairs", 8)
    max_dyn = config.get("max_dynamic_pairs", 15)
    return min_dyn, max_dyn


def calculate_correlation(price_data):
    if not price_data:
        return None
    df_combined = pd.DataFrame(price_data)
    try:
        corr_matrix = df_combined.corr(method="pearson")
        return corr_matrix
    except Exception as e:
        log(f"Error calculating correlation matrix: {e}", level="ERROR")
        return None


def select_active_symbols():
    """
    Главная функция выбора пар:
    1. Берём FIXED_PAIRS
    2. Фильтруем и отбираем dynamic
    3. Сохраняем всё в SYMBOLS_FILE (список словарей) + Telegram уведомление
    """
    auto_update_valid_pairs_if_needed()
    auto_cleanup_signal_failures()

    raw_symbols = fetch_all_symbols()
    if not raw_symbols:
        log("⚠️ fetch_all_symbols returned empty!", level="ERROR")
        return []

    all_symbols = [normalize_symbol(s) for s in raw_symbols]
    balance = get_cached_balance()
    min_dyn, max_dyn = get_pair_limits()
    fixed = FIXED_PAIRS
    priority_pairs = get_priority_small_balance_pairs() if balance < 300 else []

    # Собираем данные (ATR/volume/risk_factor) для dynamic
    sym_data = {}
    for sym in all_symbols:
        if sym in fixed:
            continue
        df_15m = fetch_symbol_data(sym, timeframe="15m", limit=100)
        if df_15m is None or len(df_15m) < 20:
            continue
        last_price = df_15m["close"].iloc[-1]
        atr_val = calculate_atr_volatility(df_15m)
        volume_usdc = df_15m["volume"].mean() * last_price

        r_factor, _ = get_symbol_risk_factor(sym)
        sym_data[sym] = {
            "atr": atr_val,
            "volume": volume_usdc,
            "last_price": last_price,
            "risk_factor": r_factor,
        }

    # Фильтруем multi-tier
    tiers = get_filter_tiers()
    filtered_data = {}
    for tier in tiers:
        filtered_data = {}
        for s, info in sym_data.items():
            if info["atr"] >= tier["atr"] and info["volume"] >= tier["volume"]:
                filtered_data[s] = info
        if len(filtered_data) >= min_dyn:
            log(f"[FilterTier] {len(filtered_data)} symbols passed ATR≥{tier['atr']} / VOL≥{tier['volume']}", level="INFO")
            break
        else:
            log(f"[FilterTier] Only {len(filtered_data)} passed => next tier...", level="INFO")

    if not filtered_data:
        # Если ни одна не проходит, используем только fixed
        log("⚠️ After all filter tiers, 0 pairs found. Using only fixed pairs...", level="WARNING")
        send_telegram_message("🚨 0 pairs passed filter tiers!", force=True)
        final_symbols_list = [{"symbol": sym, "type": "fixed"} for sym in fixed]
        save_symbols_file(final_symbols_list)
        return final_symbols_list

    # Сбор price_data для корреляции
    price_data = {}
    for s in filtered_data.keys():
        df_ = fetch_symbol_data(s, timeframe="15m", limit=80)
        if df_ is not None and len(df_) >= 2:
            price_data[s] = df_["close"].values

    corr_matrix = calculate_correlation(price_data) if len(price_data) > 1 else None

    # Составляем dynamic_list
    dynamic_list = []
    if balance < 300:
        # Для маленьких счётов
        entries = []
        for s, info in filtered_data.items():
            base_score = info["volume"] * info["risk_factor"]
            if info["last_price"] < 5:
                base_score *= 1.2

            # При желании можно сохранить reason/base_score, но пока нет
            entries.append((s, base_score))

        entries.sort(key=lambda x: x[1], reverse=True)

        final_list = []
        added = set()

        # Приоритетные пары (для малых счетов)
        for p in priority_pairs:
            if p in filtered_data:
                final_list.append(p)
                added.add(p)

        for s, sc in entries:
            if len(final_list) >= max_dyn:
                break
            if s not in added:
                if corr_matrix is not None:
                    skip = False
                    for a_ in added:
                        if s in corr_matrix.index and a_ in corr_matrix.columns:
                            if abs(corr_matrix.loc[s, a_]) > 0.9:
                                skip = True
                                break
                    if skip:
                        continue
                final_list.append(s)
                added.add(s)

        dynamic_list = final_list

    else:
        # Для больших счетов — сортируем просто volume*risk_factor + корреляция
        pairs_with_scores = []
        for s, info in filtered_data.items():
            sc = info["volume"] * info["risk_factor"]
            pairs_with_scores.append((s, sc))

        pairs_with_scores.sort(key=lambda x: x[1], reverse=True)

        uncorrelated = []
        added = set()
        for sym, sc in pairs_with_scores:
            if len(uncorrelated) >= max_dyn:
                break
            if corr_matrix is not None and len(added) > 0:
                skip = False
                for a_ in added:
                    if sym in corr_matrix.index and a_ in corr_matrix.columns:
                        if abs(corr_matrix.loc[sym, a_]) > 0.9:
                            skip = True
                            break
                if skip:
                    continue
            uncorrelated.append(sym)
            added.add(sym)

        dyn_count = max(min_dyn, min(len(uncorrelated), max_dyn))
        dynamic_list = uncorrelated[:dyn_count]

    # Собираем окончательный список
    final_symbols_list = []

    # 1) Fixed
    for fsym in fixed:
        # Хранить доп. поля? (atr, volume, etc.)
        # Пока не нужно, так как fixed не фильтруется
        final_symbols_list.append({"symbol": fsym, "type": "fixed"})

    # 2) Dynamic
    for dsym in dynamic_list:
        info = filtered_data[dsym]
        final_symbols_list.append(
            {
                "symbol": dsym,
                "type": "dynamic",
                "atr": round(info["atr"], 6),
                "volume_usdc": round(info["volume"], 2),
                "risk_factor": round(info["risk_factor"], 3),
                # при желании — last_price, base_score, reason и т.п.
            }
        )

    # Сохраняем всё
    save_symbols_file(final_symbols_list)

    # Telegram summary
    fixed_count = len(fixed)
    dyn_count = len(dynamic_list)
    msg = (
        f"🔄 Symbol rotation:\n"
        f"Balance: {balance:.1f} USDC\n"
        f"Filtered: {len(filtered_data)}\n"
        f"Fixed: {fixed_count} | Dynamic: {dyn_count}\n"
        f"Active total: {len(final_symbols_list)}"
    )
    send_telegram_message(msg, force=True)

    return final_symbols_list


def save_symbols_file(symbols_list):
    """Сохраняем список словарей (symbols) в JSON с file lock."""
    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w", encoding="utf-8") as f:
            json.dump(symbols_list, f, indent=2)
        log(f"Saved {len(symbols_list)} active symbols -> {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols: {e}", level="ERROR")


def start_symbol_rotation(stop_event):
    while not stop_event.is_set():
        try:
            update_interval = get_update_interval()
            syms = select_active_symbols()

            # Логируем, какие пары выбраны (безопасно)
            symbol_names = [extract_symbol(s) for s in syms]
            log(f"🔁 Rotation: {len(syms)} symbols → {', '.join(symbol_names)}", level="INFO")
            log(f"Next rotation in {update_interval/60:.1f} minutes", level="DEBUG")

            sleep_interval = 10
            for _ in range(int(update_interval / sleep_interval)):
                if stop_event.is_set():
                    break
                time.sleep(sleep_interval)
        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed: {e}", force=True)
            time.sleep(60)


def get_update_interval():
    balance = get_cached_balance()
    base_interval = BASE_UPDATE_INTERVAL

    if balance < 120:
        account_factor = 0.75
    elif balance < 200:
        account_factor = 0.9
    else:
        account_factor = 1.0

    hour_factor = 0.75 if is_optimal_trading_hour() else 1.0
    market_volatility = get_market_volatility_index()
    if market_volatility > 1.5:
        volatility_factor = 0.7
    elif market_volatility > 1.2:
        volatility_factor = 0.85
    else:
        volatility_factor = 1.0

    final_interval = max(BASE_UPDATE_INTERVAL, int(base_interval * account_factor * hour_factor * volatility_factor))
    return final_interval


def track_missed_opportunities():
    """Заглушка для анализа пропущенных 'ракет'."""
    pass
