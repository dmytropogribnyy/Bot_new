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
from core.legacy.binance_api import convert_symbol
from core.legacy.exchange_init import exchange
from core.legacy.fail_stats_tracker import FAIL_STATS_FILE, get_symbol_risk_factor
from core.legacy.strategy import fetch_data_multiframe  # убедись, что импорт есть
from telegram.telegram_utils import send_telegram_message
from utils_core import (
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

BLOCKED_SYMBOLS_FILE = "data/blocked_symbols.json"
LOW_VOLUME_FILE = "data/low_volume_hits.json"


def load_blocked_symbols():
    try:
        if os.path.exists(BLOCKED_SYMBOLS_FILE):
            with open(BLOCKED_SYMBOLS_FILE) as f:
                return json.load(f)
    except Exception as e:
        log(f"[Blocked] Failed to load blocked symbols: {e}", level="WARNING")
    return {}


def save_blocked_symbols(data):
    try:
        os.makedirs(os.path.dirname(BLOCKED_SYMBOLS_FILE), exist_ok=True)
        with open(BLOCKED_SYMBOLS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log(f"[Blocked] Failed to save blocked symbols: {e}", level="ERROR")


def load_low_volume_hits():
    try:
        if os.path.exists(LOW_VOLUME_FILE):
            with open(LOW_VOLUME_FILE) as f:
                return json.load(f)
    except Exception as e:
        log(f"[LowVolume] Failed to load low_volume_hits: {e}", level="WARNING")
    return {}


def save_low_volume_hits(data):
    try:
        os.makedirs(os.path.dirname(LOW_VOLUME_FILE), exist_ok=True)
        with open(LOW_VOLUME_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log(f"[LowVolume] Failed to save low_volume_hits: {e}", level="ERROR")


def auto_update_valid_pairs_if_needed():
    """
    Обновляет valid_usdc_symbols.json каждые 1 час через test_api.py,
    если флаг disable_test_api_autorun не активирован.
    """
    from utils_core import get_runtime_config

    config = get_runtime_config()
    if config.get("disable_test_api_autorun", False):
        log("⏭️ test_api.py auto-run disabled via config", level="INFO")
        return

    last_updated_path = Path("data/valid_usdc_last_updated.txt")
    now = int(time.time())

    if last_updated_path.exists():
        with last_updated_path.open("r") as f:
            last_time = int(f.read().strip())
            if now - last_time < 3600:
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
        with open(FAIL_STATS_FILE) as f:
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
    """
    Расчёт корреляционной матрицы для списка пар.
    Нормализует массивы по длине, игнорирует повреждённые, избегает ошибок.
    """
    import numpy as np
    import pandas as pd

    from utils_logging import log

    if not price_data:
        log("[CorrMatrix] Empty price_data input", level="WARNING")
        return None

    # 🔒 Проверка длины массивов
    lengths = [len(v) for v in price_data.values() if isinstance(v, list | np.ndarray) and len(v) >= 2]
    if not lengths:
        log("[CorrMatrix] No valid price data arrays found", level="WARNING")
        return None

    min_len = min(lengths)
    if len(set(lengths)) > 1:
        log(f"[CorrMatrix] Normalizing arrays to min_len={min_len}", level="WARNING")

    # 🧹 Обрезаем все массивы до одинаковой длины
    normalized_data = {}
    for k, v in price_data.items():
        if isinstance(v, list | np.ndarray) and len(v) >= min_len:
            normalized_data[k] = v[-min_len:]

    if len(normalized_data) < 2:
        log("[CorrMatrix] Too few valid arrays after normalization", level="WARNING")
        return None

    try:
        df_combined = pd.DataFrame(normalized_data)
        corr_matrix = df_combined.corr(method="pearson")
        return corr_matrix
    except Exception as e:
        log(f"[CorrMatrix] Error calculating correlation matrix: {e}", level="ERROR")
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

    # Загружаем список qty_blocked
    blocked_symbols = load_blocked_symbols()
    blocked_list = [s for s, count in blocked_symbols.items() if count >= 3]
    if blocked_list:
        log(f"[Selector] ❌ Excluding {len(blocked_list)} blocked symbols: {', '.join(blocked_list)}", level="WARNING")

    # Собираем данные (ATR/volume/risk_factor) для dynamic
    sym_data = {}
    for sym in all_symbols:
        if sym in fixed:
            continue
        if sym in blocked_list:
            continue
        df = fetch_data_multiframe(sym)
        if df is None:
            log(f"[Selector] Skipping {sym} — fetch_data_multiframe returned None", level="WARNING")
            continue
        if len(df) < 20:
            log(f"[Selector] Skipping {sym} — not enough data rows ({len(df)})", level="DEBUG")
            continue
        last_price = df["close"].iloc[-1]
        atr_val = df["atr"].iloc[-1]
        volume_usdc = df["volume"].mean() * last_price
        r_factor, _ = get_symbol_risk_factor(sym)

        sym_data[sym] = {
            "atr": atr_val,
            "volume": volume_usdc,
            "last_price": last_price,
            "risk_factor": r_factor,
        }

    # Обновляем low_volume_hits
    low_volume_hits = load_low_volume_hits()
    current_time = time.time()
    keep_duration = 6 * 3600
    tiers = get_filter_tiers()

    for s in list(sym_data.keys()):
        vol = sym_data[s]["volume"]
        atr = sym_data[s]["atr"]
        passed = any(vol >= t["volume"] and atr >= t["atr"] for t in tiers)

        if not passed:
            if s not in low_volume_hits:
                low_volume_hits[s] = {"count": 1, "last": current_time}
            else:
                low_volume_hits[s]["count"] += 1
                low_volume_hits[s]["last"] = current_time
        else:
            if s in low_volume_hits:
                del low_volume_hits[s]

    low_volume_hits = {k: v for k, v in low_volume_hits.items() if current_time - v.get("last", 0) < keep_duration}
    save_low_volume_hits(low_volume_hits)

    excluded_lv = [s for s, v in low_volume_hits.items() if v["count"] >= 4]
    if excluded_lv:
        log(
            f"[LowVolume] ❌ Excluding {len(excluded_lv)} low-volume repeat offenders: {', '.join(excluded_lv)}",
            level="WARNING",
        )
        for s in excluded_lv:
            sym_data.pop(s, None)

    # Фильтруем multi-tier
    filtered_data = {}
    for tier in tiers:
        filtered_data = {
            s: info for s, info in sym_data.items() if info["atr"] >= tier["atr"] and info["volume"] >= tier["volume"]
        }
        if len(filtered_data) >= min_dyn:
            log(
                f"[FilterTier] {len(filtered_data)} symbols passed ATR≥{tier['atr']} / VOL≥{tier['volume']}",
                level="INFO",
            )
            break
        else:
            log(f"[FilterTier] Only {len(filtered_data)} passed => next tier...", level="INFO")

    if not filtered_data:
        log("⚠️ After all filter tiers, 0 pairs found. Using only fixed pairs...", level="WARNING")
        send_telegram_message("🚨 0 pairs passed filter tiers!", force=True)
        final_symbols_list = [{"symbol": sym, "type": "fixed"} for sym in fixed]
        save_symbols_file(final_symbols_list)
        return final_symbols_list

    # Сбор price_data для корреляции
    price_data = {}
    for s in filtered_data.keys():
        df_ = fetch_data_multiframe(s)
        if df_ is not None and len(df_) >= 2:
            price_data[s] = df_["close"].values

    corr_matrix = calculate_correlation(price_data) if len(price_data) > 1 else None

    # Составляем dynamic_list
    dynamic_list = []
    if balance < 300:
        entries = []
        for s, info in filtered_data.items():
            base_score = info["volume"] * info["risk_factor"]
            if info["last_price"] < 5:
                base_score *= 1.2
            entries.append((s, base_score))

        entries.sort(key=lambda x: x[1], reverse=True)
        final_list = []
        added = set()

        for p in priority_pairs:
            if p in filtered_data:
                final_list.append(p)
                added.add(p)

        for s, _sc in entries:
            if len(final_list) >= max_dyn:
                break
            if s not in added:
                if corr_matrix is not None:
                    if any(abs(corr_matrix.loc[s, a_]) > 0.9 for a_ in added if s in corr_matrix and a_ in corr_matrix):
                        continue
                final_list.append(s)
                added.add(s)

        dynamic_list = final_list

    else:
        pairs_with_scores = [(s, info["volume"] * info["risk_factor"]) for s, info in filtered_data.items()]
        pairs_with_scores.sort(key=lambda x: x[1], reverse=True)
        uncorrelated = []
        added = set()

        for sym, _sc in pairs_with_scores:
            if len(uncorrelated) >= max_dyn:
                break
            if corr_matrix is not None and any(
                abs(corr_matrix.loc[sym, a_]) > 0.9 for a_ in added if sym in corr_matrix and a_ in corr_matrix
            ):
                continue
            uncorrelated.append(sym)
            added.add(sym)

        dyn_count = max(min_dyn, min(len(uncorrelated), max_dyn))
        dynamic_list = uncorrelated[:dyn_count]

    # 🔔 Уведомление, если не хватило пар
    if len(dynamic_list) < min_dyn:
        send_telegram_message(
            f"⚠️ Only {len(dynamic_list)} dynamic pairs selected (min required: {min_dyn}) — check volume/atr tiers.",
            force=True,
        )

    # Финальный список символов
    final_symbols_list = [{"symbol": fsym, "type": "fixed"} for fsym in fixed]

    for dsym in dynamic_list:
        info = filtered_data[dsym]
        final_symbols_list.append(
            {
                "symbol": dsym,
                "type": "dynamic",
                "atr": round(info["atr"], 6),
                "volume_usdc": round(info["volume"], 2),
                "risk_factor": round(info["risk_factor"], 3),
            }
        )

    save_symbols_file(final_symbols_list)

    msg = f"🔄 Symbol rotation:\nBalance: {balance:.1f} USDC\nFiltered: {len(filtered_data)}\nFixed: {len(fixed)} | Dynamic: {len(dynamic_list)}\nActive total: {len(final_symbols_list)}"
    send_telegram_message(msg, force=True)

    log(
        f"[Selector] Selected {len(final_symbols_list)} total symbols ({len(fixed)} fixed, {len(dynamic_list)} dynamic)",
        level="INFO",
    )
    log(f"[Selector] Top dynamic symbols: {', '.join(dynamic_list[:5])}", level="DEBUG")

    return final_symbols_list


def save_symbols_file(symbols_list):
    """Сохраняет список словарей (symbols) в JSON с file lock."""
    import json
    import os

    from utils_logging import log

    try:
        if not symbols_list:
            log("⚠️ Attempted to save empty symbols list!", level="WARNING")

        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w", encoding="utf-8") as f:
            json.dump(symbols_list, f, indent=2, ensure_ascii=False)
        log(f"[Save] {len(symbols_list)} symbols saved to → {SYMBOLS_FILE}", level="INFO")

    except (TypeError, ValueError) as json_error:
        log(f"[Save] ❌ Error serializing symbols: {json_error}", level="ERROR")
    except Exception as e:
        log(f"[Save] ❌ Error saving active symbols: {e}", level="ERROR")


def start_symbol_rotation(stop_event):
    from datetime import datetime

    while not stop_event.is_set():
        try:
            log(f"[Rotation] 🔄 Starting rotation at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", level="DEBUG")

            update_interval = get_update_interval()
            syms = select_active_symbols()

            # Логируем, какие пары выбраны
            symbol_names = [extract_symbol(s) for s in syms]
            log(f"[Rotation] ✅ Selected {len(syms)} symbols: {', '.join(symbol_names)}", level="INFO")
            log(f"[Rotation] ⏱ Next update in {update_interval / 60:.1f} minutes", level="DEBUG")

            # 💾 Пишем в файл последнюю ротацию (можно использовать UI/отладку)
            try:
                with open("data/last_symbol_rotation.json", "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "count": len(symbol_names),
                            "symbols": symbol_names,
                            "next_check_in_minutes": round(update_interval / 60, 1),
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
            except Exception as e:
                log(f"[Rotation] Failed to write last_symbol_rotation.json: {e}", level="WARNING")

            # ⏲ Ожидаем до следующей ротации
            sleep_interval = 10
            for _ in range(int(update_interval / sleep_interval)):
                if stop_event.is_set():
                    log("[Rotation] ❌ Stop signal received. Exiting rotation loop.", level="INFO")
                    send_telegram_message("🔁 Symbol rotation loop stopped", force=True)
                    return
                time.sleep(sleep_interval)

        except Exception as e:
            log(f"[Rotation] ❌ Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed:\n{e}", force=True)
            time.sleep(60)


def get_update_interval():
    balance = get_cached_balance()
    base_interval = BASE_UPDATE_INTERVAL if BASE_UPDATE_INTERVAL else 900  # fallback: 15 min

    # 🔢 Адаптация по балансу
    if balance < 120:
        account_factor = 0.75
    elif balance < 200:
        account_factor = 0.9
    else:
        account_factor = 1.0

    # ⏰ Адаптация по времени суток
    hour_factor = 0.75 if is_optimal_trading_hour() else 1.0

    # 📊 Адаптация по рыночной волатильности
    market_volatility = get_market_volatility_index()
    if market_volatility > 1.5:
        volatility_factor = 0.7
    elif market_volatility > 1.2:
        volatility_factor = 0.85
    else:
        volatility_factor = 1.0

    final_interval = max(base_interval, int(base_interval * account_factor * hour_factor * volatility_factor))

    # 📋 Лог всех расчётов
    from utils_logging import log

    log(
        f"[UpdateInterval] balance={balance:.2f}, account_factor={account_factor}, "
        f"hour_factor={hour_factor}, vol={market_volatility:.2f}, vol_factor={volatility_factor}, "
        f"→ interval={final_interval / 60:.1f} min",
        level="DEBUG",
    )

    return final_interval


CACHE_FILE = "data/missed_opportunities.json"
CACHE_LOCK = Lock()
MAX_ENTRIES = 200


def track_missed_opportunities():
    """Анализирует символы, которые сильно выросли за 24ч, но не были отобраны."""
    from datetime import datetime

    from pair_selector import fetch_all_symbols  # или список конкретных символов
    from utils_logging import log

    symbols = fetch_all_symbols()

    for symbol in symbols:
        try:
            symbol = extract_symbol(symbol)
            df = fetch_data_multiframe(symbol)
            if df is None or len(df) < 20:
                continue

            price_24h_ago = df["close"].iloc[0]
            price_now = df["close"].iloc[-1]
            potential_profit = ((price_now - price_24h_ago) / price_24h_ago) * 100

            if abs(potential_profit) < 5:
                log(f"[MissedTracker] {symbol} ignored: gain={potential_profit:.2f}%", level="DEBUG")
                continue  # не ракета

            atr_vol = df["atr"].iloc[-1]
            avg_volume = df["volume"].iloc[-96:].mean() if len(df) >= 96 else df["volume"].mean()
            now = datetime.utcnow().isoformat()

            entry = {
                "symbol": symbol,
                "timestamp": now,
                "profit": round(potential_profit, 2),
                "atr_vol": round(atr_vol, 4),
                "avg_volume": round(avg_volume),
            }

            with CACHE_LOCK:
                cache = []
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE) as f:
                        try:
                            cache = json.load(f)
                        except json.JSONDecodeError:
                            log(f"[MissedTracker] Failed to parse {CACHE_FILE}", level="WARNING")

                cache.append(entry)
                cache = cache[-MAX_ENTRIES:]

                with open(CACHE_FILE, "w") as f:
                    json.dump(cache, f, indent=2)

            log(f"[MissedTracker] 🚀 Missed opportunity: {symbol} +{entry['profit']}%", level="INFO")

        except Exception as e:
            log(f"[MissedTracker] ❌ Error processing {symbol}: {e}", level="ERROR")
