# pair_selector.py
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

import pandas as pd

from common.config_loader import (
    FIXED_PAIRS,
    MISSED_OPPORTUNITIES_FILE,
    PAIR_COOLING_PERIOD_HOURS,
    PAIR_ROTATION_MIN_INTERVAL,
    USDC_SYMBOLS,
    USDT_SYMBOLS,
    USE_TESTNET,
    get_priority_small_balance_pairs,
)
from constants import PERFORMANCE_FILE, SIGNAL_FAILURES_FILE, SYMBOLS_FILE
from core.binance_api import convert_symbol
from core.exchange_init import exchange
from core.fail_stats_tracker import FAIL_STATS_FILE, get_symbol_risk_factor
from core.priority_evaluator import generate_priority_pairs, save_priority_pairs
from symbol_activity_tracker import SIGNAL_ACTIVITY_FILE
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, get_market_volatility_index, get_runtime_config, is_optimal_trading_hour, load_json_file, normalize_symbol, safe_call_retry, save_json_file
from utils_logging import log  # или ваш метод логирования

# Adaptive rotation interval - more frequent for small accounts and high volatility
BASE_UPDATE_INTERVAL = 60 * 15  # 15 минут вместо 30
symbols_file_lock = Lock()
performance_lock = Lock()

DRY_RUN_FALLBACK_SYMBOLS = USDT_SYMBOLS if USE_TESTNET else USDC_SYMBOLS

# Historical performance tracking
pair_performance = {}

# Добавить глобальную переменную
_last_logged_hour = None


def auto_update_valid_pairs_if_needed():
    """
    Если прошло >6 часов с последнего обновления valid_usdc_symbols.json,
    запускает test_api.py, логирует результат и при успехе
    записывает текущее время в data/valid_usdc_last_updated.txt.
    """
    last_updated_path = Path("data/valid_usdc_last_updated.txt")
    now = int(time.time())

    # Проверяем, не прошло ли менее 6 часов
    if last_updated_path.exists():
        with last_updated_path.open("r") as f:
            last_time = int(f.read().strip())
            if now - last_time < 6 * 3600:
                return  # Ещё слишком рано, выходим

    print("🕒 Valid USDC symbols outdated — running test_api.py")

    # Запускаем test_api.py через sys.executable
    result = subprocess.call([sys.executable, "test_api.py"])
    if result != 0:
        log("[Updater] test_api.py failed to execute", level="ERROR")
    else:
        log("[Updater] test_api.py completed successfully", level="INFO")

    # Проверяем, создался ли valid_usdc_symbols.json
    valid_file = Path("data/valid_usdc_symbols.json")
    if not valid_file.exists():
        log("⚠️ valid_usdc_symbols.json was not created!", level="ERROR")
        return

    # При успешном создании valid_usdc_symbols.json пишем текущее время
    # чтобы не дергать test_api.py раньше, чем через 6 часов
    with last_updated_path.open("w") as f:
        f.write(str(now))


def get_filter_tiers():
    config = get_runtime_config()
    return config.get("FILTER_TIERS", [{"atr": 0.006, "volume": 600}, {"atr": 0.005, "volume": 500}, {"atr": 0.004, "volume": 400}, {"atr": 0.003, "volume": 300}])


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
    Возвращает список USDC-пар из valid_usdc_symbols.json.
    Если файл не найден или пуст — fallback на USDC_SYMBOLS.
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
    """Fetch OHLCV data for a symbol."""
    try:
        api_symbol = convert_symbol(symbol)
        ohlcv = safe_call_retry(exchange.fetch_ohlcv, api_symbol, timeframe, limit=limit, label=f"fetch_ohlcv {symbol}")
        if not ohlcv:
            log(f"No OHLCV data returned for {symbol}", level="ERROR")
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def auto_cleanup_signal_failures(threshold=5000, keep_last=1000):
    try:
        if os.path.exists(SIGNAL_FAILURES_FILE):
            data = load_json_file(SIGNAL_FAILURES_FILE)
            if isinstance(data, list) and len(data) > threshold:
                trimmed = data[-keep_last:]
                save_json_file(SIGNAL_FAILURES_FILE, trimmed)
                log(f"🧹 Auto-cleaned signal_failures.json: kept last {keep_last} of {len(data)} entries", level="INFO")
    except Exception as e:
        log(f"⚠️ Error during auto-cleanup of signal_failures.json: {e}", level="ERROR")


def calculate_volatility(df):
    """Calculate volatility based on price range."""
    if df is None or len(df) < 2:
        return 0
    df["range"] = df["high"] - df["low"]
    return df["range"].mean() / df["close"].mean()


def calculate_atr_volatility(df, period=14):
    """Calculate ATR-based volatility."""
    if df is None or len(df) < period + 1:
        return 0

    # Calculate True Range
    df["tr1"] = abs(df["high"] - df["low"])
    df["tr2"] = abs(df["high"] - df["close"].shift(1))
    df["tr3"] = abs(df["low"] - df["close"].shift(1))
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

    # Calculate ATR
    df["atr"] = df["tr"].rolling(period).mean()

    if len(df) > period and not pd.isna(df["atr"].iloc[-1]):
        return df["atr"].iloc[-1] / df["close"].iloc[-1]
    else:
        return 0


def calculate_short_term_metrics(df):
    """
    Calculate short-term trading metrics for pair evaluation.

    Args:
        df: DataFrame with OHLCV data

    Returns:
        Dictionary with short-term metrics
    """
    if df is None or len(df) < 20:
        return {"momentum": 0, "volatility_ratio": 1, "volume_trend": 0, "rsi_signal": 0, "price_trend": 0}

    try:
        # Short-term momentum (last 6 candles vs previous 6)
        recent_close = df["close"].iloc[-6:].mean()
        previous_close = df["close"].iloc[-12:-6].mean()
        momentum = (recent_close / previous_close - 1) * 100

        # Volatility ratio (recent vs historical)
        recent_range = (df["high"].iloc[-6:] - df["low"].iloc[-6:]).mean()
        historical_range = (df["high"].iloc[-24:-6] - df["low"].iloc[-24:-6]).mean()
        volatility_ratio = recent_range / historical_range if historical_range > 0 else 1

        # Volume trend
        recent_volume = df["volume"].iloc[-6:].mean()
        previous_volume = df["volume"].iloc[-12:-6].mean()
        volume_trend = recent_volume / previous_volume if previous_volume > 0 else 1

        # Basic RSI calculation
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # RSI direction signal (-1 to 1 scale)
        rsi_signal = 0
        if not pd.isna(rsi.iloc[-1]) and not pd.isna(rsi.iloc[-2]):
            if rsi.iloc[-1] < 30:
                rsi_signal = 1  # Potential oversold (bullish)
            elif rsi.iloc[-1] > 70:
                rsi_signal = -1  # Potential overbought (bearish)

        # Recent price trend direction
        price_direction = df["close"].iloc[-1] > df["close"].iloc[-5]
        price_trend = 1 if price_direction else -1

        return {"momentum": momentum, "volatility_ratio": volatility_ratio, "volume_trend": volume_trend, "rsi_signal": rsi_signal, "price_trend": price_trend}
    except Exception as e:
        log(f"Error calculating short-term metrics: {e}", level="ERROR")
        return {"momentum": 0, "volatility_ratio": 1, "volume_trend": 0, "rsi_signal": 0, "price_trend": 0}


def calculate_correlation(price_data):
    """
    Calculate correlation matrix between pairs to avoid selecting highly correlated assets.

    Args:
        price_data: Dictionary with symbol -> price series

    Returns:
        DataFrame with correlation matrix
    """
    if not price_data:
        return None

    # Create DataFrame with all price series
    df_combined = pd.DataFrame(price_data)

    # Calculate correlation matrix
    try:
        corr_matrix = df_combined.corr(method="pearson")
        return corr_matrix
    except Exception as e:
        log(f"Error calculating correlation matrix: {e}", level="ERROR")
        return None


def load_pair_performance():
    """Load historical performance data for pairs."""
    global pair_performance

    try:
        if os.path.exists(PERFORMANCE_FILE):
            with performance_lock, open(PERFORMANCE_FILE, "r") as f:
                pair_performance = json.load(f)
        else:
            pair_performance = {}
    except Exception as e:
        log(f"Error loading pair performance data: {e}", level="ERROR")
        pair_performance = {}


def save_pair_performance():
    """Save historical performance data for pairs."""
    try:
        with performance_lock, open(PERFORMANCE_FILE, "w") as f:
            json.dump(pair_performance, f)
    except Exception as e:
        log(f"Error saving pair performance data: {e}", level="ERROR")


def update_pair_performance(symbol, win=None, pnl=None):
    """Update performance data for a specific pair."""
    global pair_performance

    load_pair_performance()

    with performance_lock:
        if symbol not in pair_performance:
            pair_performance[symbol] = {"total_trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "last_traded": None}

        if win is not None:
            pair_performance[symbol]["total_trades"] += 1
            if win:
                pair_performance[symbol]["wins"] += 1
            else:
                pair_performance[symbol]["losses"] += 1

        if pnl is not None:
            pair_performance[symbol]["pnl"] += pnl

        pair_performance[symbol]["last_traded"] = datetime.now().isoformat()

    save_pair_performance()


def get_performance_score(symbol):
    """
    Calculate performance score for a pair based on historical results.
    Uses PAIR_COOLING_PERIOD_HOURS for recency calculation and cooling period.

    Args:
        symbol: Trading symbol to evaluate

    Returns:
        float: Performance score (0.0-1.0) with higher being better
    """
    global pair_performance

    if symbol not in pair_performance:
        return 0

    data = pair_performance[symbol]

    # If fewer than 3 trades, return neutral score
    if data.get("total_trades", 0) < 3:
        return 0

    # Calculate win rate
    wins = data.get("wins", 0)
    total_trades = data.get("total_trades", 1)  # Avoid division by zero
    win_rate = wins / total_trades if total_trades > 0 else 0

    # Calculate average PnL
    avg_pnl = data.get("pnl", 0) / total_trades if total_trades > 0 else 0

    # Calculate recency factor using PAIR_COOLING_PERIOD_HOURS
    last_traded = datetime.fromisoformat(data.get("last_traded", datetime.min.isoformat())) if data.get("last_traded") else datetime.min
    hours_since_traded = (datetime.now() - last_traded).total_seconds() / 3600

    # Full weight if traded within the configured cooling period
    recency_factor = max(0, 1 - (hours_since_traded / PAIR_COOLING_PERIOD_HOURS))

    # Base score: 60% win rate, 20% profit, 20% recency
    score = (win_rate * 0.6) + (min(1, avg_pnl) * 0.2) + (recency_factor * 0.2)

    # Check for cooling period (3+ consecutive losses)
    # If the pair has had 3 or more consecutive losses, reduce its score
    last_3_trades_were_losses = False
    if "trade_history" in data and len(data.get("trade_history", [])) >= 3:
        last_3 = data["trade_history"][-3:]
        last_3_trades_were_losses = all(not trade.get("win", False) for trade in last_3)

        # Check if still in cooling period based on time since last trade
        if last_3_trades_were_losses and hours_since_traded < PAIR_COOLING_PERIOD_HOURS:
            log(f"{symbol} in cooling period: {hours_since_traded:.1f} of {PAIR_COOLING_PERIOD_HOURS} hours after 3+ losses", level="DEBUG")
            score *= 0.5  # Reduce score by 50% during cooling period

    return score


def update_priority_pairs(force=False):
    """
    Update priority pairs periodically.

    Args:
        force: Force update regardless of time elapsed

    Returns:
        bool: Success status
    """
    try:
        # Check last update time to avoid frequent regeneration
        import json
        import os
        from datetime import datetime

        PRIORITY_JSON_PATH = "data/priority_pairs.json"
        update_needed = True

        if not force and os.path.exists(PRIORITY_JSON_PATH):
            try:
                with open(PRIORITY_JSON_PATH, "r") as f:
                    data = json.load(f)
                last_update = datetime.fromisoformat(data.get("updated_at", "2000-01-01T00:00:00"))
                hours_since_update = (datetime.now() - last_update).total_seconds() / 3600

                # Only update if more than 6 hours have passed
                update_needed = hours_since_update >= 6

                if not update_needed:
                    log(f"[PriorityUpdate] Last update was {hours_since_update:.1f} hours ago, skipping", level="DEBUG")
            except Exception as e:
                log(f"[PriorityUpdate] Error checking update time: {e}", level="WARNING")
                update_needed = True

        if update_needed or force:
            pairs = generate_priority_pairs()
            if pairs:
                save_priority_pairs(pairs)
                log("[PriorityUpdate] Priority pairs updated successfully", level="INFO")
                return True

        return False
    except Exception as e:
        log(f"[PriorityUpdate] Error updating priority pairs: {e}", level="ERROR")
        return False


def select_active_symbols():
    """
    Select the most promising symbols for trading.
    Enhanced with graduated risk approach and multi-tier filtering.
    But now we ONLY filter by ATR/Volume — no performance score filtering.
    """
    # Initialize rejection tracking
    rejected_pairs = {}
    recovery_triggered = False  # Flag to prevent duplicate logging

    # 1) Подготовка исторической статистики и конфигов
    load_pair_performance()
    update_priority_pairs()

    runtime_config = get_runtime_config()
    max_failures_per_symbol = runtime_config.get("FAILURE_BLOCK_THRESHOLD", 30)
    failure_penalty = 0.2

    failure_stats = load_failure_stats()
    missed_data = load_json_file(MISSED_OPPORTUNITIES_FILE, default={})
    activity_data = load_json_file(SIGNAL_ACTIVITY_FILE, default={})

    # 2) Загружаем список всех символов
    raw_symbols = fetch_all_symbols()
    if not raw_symbols:
        log("⚠️ fetch_all_symbols returned empty, aborting symbol selection.", level="ERROR")
        return []

    all_symbols = [normalize_symbol(s) for s in raw_symbols]

    # 3) Мониторинг процента high_risk (только лог и телеграм)
    high_risk_count = 0
    high_risk_details = []
    for symbol in all_symbols:
        risk_factor, block_info = get_symbol_risk_factor(symbol)
        if risk_factor < 0.25:
            high_risk_count += 1
            failures = block_info.get("total_failures", 0) if block_info else 0
            high_risk_details.append(f"{symbol} ({failures} failures, risk={risk_factor:.2f})")

    risk_ratio = high_risk_count / len(all_symbols)
    # Если нужно — отправляем предупреждение
    if risk_ratio >= 0.3:
        msg = f"⚠️ High risk: {high_risk_count}/{len(all_symbols)} symbols " f"({risk_ratio:.1%}) have risk<0.25"
        send_telegram_message(msg, force=True)
        log(msg, level="WARNING")

    # 4) Считываем лимиты min_dyn / max_dyn, адаптируем по волатильности
    balance = get_cached_balance()
    min_dyn, max_dyn = get_pair_limits()
    market_volatility = get_market_volatility_index()

    if market_volatility > 1.5:  # слишком высокая волатильность
        max_dyn = min(max_dyn, 4)
        log(f"Market volatility high ({market_volatility:.2f}) => max_dyn={max_dyn}", level="INFO")
    elif market_volatility < 0.8:  # очень тихий рынок
        min_dyn = min(min_dyn + 2, max_dyn)
        log(f"Market volatility low ({market_volatility:.2f}) => min_dyn={min_dyn}", level="INFO")

    log(f"Adaptive pair limits: min={min_dyn}, max={max_dyn}", level="INFO")

    fixed = FIXED_PAIRS
    priority_pairs = get_priority_small_balance_pairs() if balance < 300 else []

    dynamic_data = {}
    # 5) Собираем данные для всех символов (risk_factor, performance_score, atr, volume)
    for symbol in all_symbols:
        if symbol in fixed:
            # Просто отметим причину (fixed_pair), но позже всё равно добавим
            rejected_pairs[symbol] = "fixed_pair"
            continue

        risk_factor, block_info = get_symbol_risk_factor(symbol)
        if risk_factor < 0.25:
            log(f"{symbol} has high risk factor: {risk_factor:.2f}", level="WARNING")

        df_15m = fetch_symbol_data(symbol, timeframe="15m", limit=100)
        if df_15m is None or len(df_15m) < 20:
            rejected_pairs[symbol] = "insufficient_data"
            continue

        # Расчёт метрик
        last_price = df_15m["close"].iloc[-1]
        vol = calculate_volatility(df_15m)
        atr_val = calculate_atr_volatility(df_15m)
        volume_usdc = df_15m["volume"].mean() * last_price

        st_metrics = calculate_short_term_metrics(df_15m)
        perf_score = get_performance_score(symbol)  # Не фильтруем, но оставим для сортировки

        # Собираем "динамические" поля
        dynamic_data[symbol] = {
            "atr_percent": atr_val,  # atr / close
            "volume": volume_usdc,
            "volatility_score": vol,
            "price": last_price,
            "momentum": st_metrics["momentum"],
            "volatility_ratio": st_metrics["volatility_ratio"],
            "volume_trend": st_metrics["volume_trend"],
            "rsi_signal": st_metrics["rsi_signal"],
            "price_trend": st_metrics["price_trend"],
            "performance_score": perf_score,
            "risk_factor": risk_factor,
        }

        # boost missed opportunities
        if symbol in missed_data and missed_data[symbol].get("count", 0) >= 2:
            dynamic_data[symbol]["performance_score"] += 0.2

        # boost activity
        activity_count = len(activity_data.get(symbol, []))
        if activity_count >= 10:
            bonus = 0.1 + min(activity_count / 100, 0.2)
            dynamic_data[symbol]["performance_score"] += bonus

        # penalty by failures
        total_failures = sum(failure_stats.get(symbol, {}).values())
        if total_failures >= max_failures_per_symbol:
            penalty = failure_penalty * (total_failures / max_failures_per_symbol)
            dynamic_data[symbol]["performance_score"] = max(dynamic_data[symbol]["performance_score"] - penalty, 0)

    # 6) Фильтрация ТОЛЬКО по ATR/Volume (multi-tier)
    tiers = get_filter_tiers()  # user function returning list of {"atr":..., "volume":...}
    filtered_data = {}

    for tier in tiers:
        filtered_data = {}
        for sym, info in dynamic_data.items():
            atr_p = info["atr_percent"]  # доля: 0.006 => 0.6%
            vol_usdc = info["volume"]
            if atr_p >= tier["atr"] and vol_usdc >= tier["volume"]:
                filtered_data[sym] = info
            else:
                reason = "low_volatility" if atr_p < tier["atr"] else "low_volume"
                rejected_pairs[sym] = reason

        if len(filtered_data) >= min_dyn:
            log(f"[FilterTier] {len(filtered_data)} symbols passed ATR≥{tier['atr']}, VOL≥{tier['volume']}", level="INFO")
            break
        else:
            log(f"[FilterTier] Only {len(filtered_data)} passed => trying next tier...", level="INFO")

    if not filtered_data:
        log("⚠️ After all tiers, still no pairs found for trading", level="WARNING")

    # 7) Корреляция, small vs large account, fallback
    #    — логика та же, только берём pairs из filtered_data.
    #    (см. оригинальный код)
    price_data = {}
    for sym in filtered_data.keys():
        df_ = fetch_symbol_data(sym, timeframe="15m", limit=100)
        if df_ is not None and len(df_) >= 2:
            price_data[sym] = df_["close"].values

    corr_matrix = calculate_correlation(price_data) if len(price_data) > 1 else None

    # ----- Пример: small vs large account -----
    if balance < 300:
        # Собираем финальный «оценочный» балл (short_term_score) + performance_score
        sorted_dyn = []
        for s, data in filtered_data.items():
            st_score = data["momentum"] * 0.4 + data["volume_trend"] * 0.3 + data["performance_score"] * 2 + data["rsi_signal"] * 0.5
            # micro-trade preference
            micro_bonus = 0
            if data["price"] < 1:
                micro_bonus += 3
            elif data["price"] < 10:
                micro_bonus += 2
            elif data["price"] < 50:
                micro_bonus += 1
            st_score += micro_bonus * 0.5

            price_factor = 1 / (data["price"] + 0.1)
            risk_factor = data["risk_factor"]
            final_score = st_score * price_factor * risk_factor

            sorted_dyn.append((s, final_score))

        # Сортируем
        sorted_dyn.sort(key=lambda x: x[1], reverse=True)

        # Первым делом — priority_pairs
        final_pairs = []
        for p in priority_pairs:
            if p in filtered_data:
                final_pairs.append(p)

        added = set(final_pairs)
        slots = min(min_dyn, max_dyn) - len(final_pairs)
        for sym, sc in sorted_dyn:
            if slots <= 0:
                break
            if sym in added or sym in fixed:
                continue

            # коррел. проверка
            if corr_matrix is not None and len(added) > 0:
                skip = False
                for already in added:
                    if sym in corr_matrix.index and already in corr_matrix.columns:
                        if abs(corr_matrix.loc[sym, already]) > 0.9:
                            skip = True
                            break
                if skip:
                    continue

            final_pairs.append(sym)
            added.add(sym)
            slots -= 1

        selected_dyn = final_pairs

    else:
        # Для больших аккаунтов - используем «composite_score»
        pairs_with_scores = []
        for s, data in filtered_data.items():
            risk_factor = data["risk_factor"]
            cscore = (data["volatility_score"] * data["volume"] * 0.5 + data["momentum"] * 3 + data["performance_score"] * 0.2) * risk_factor
            pairs_with_scores.append((s, cscore))

        pairs_with_scores.sort(key=lambda x: x[1], reverse=True)

        uncorrelated = []
        added = set()
        for sym, sc in pairs_with_scores:
            if sym in added:
                continue
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
            if len(uncorrelated) >= max_dyn:
                break

        # Final dynamic
        dyn_count = max(min_dyn, min(len(uncorrelated), max_dyn))
        selected_dyn = uncorrelated[:dyn_count]

    # 8) Объединяем fixed + selected_dyn
    active_symbols = list(fixed) + selected_dyn

    # При необходимости fallback (если меньше 5)
    MIN_ACTIVE_PAIRS = 5
    if len(active_symbols) < MIN_ACTIVE_PAIRS and not recovery_triggered:
        recovery_triggered = True
        log(f"⚠️ Only {len(active_symbols)} active symbols => fallback approach", level="WARNING")
        # Здесь можно подключить «absolute fallback» или inactive_candidates.json

    # 9) Инициализация relax_factor и финальные логи
    try:
        filter_path = "data/filter_adaptation.json"
        filter_data = load_json_file(filter_path, default={})
        updated = False

        for sym in active_symbols:
            norm_ = sym.replace("/", "").upper()
            if norm_ not in filter_data:
                filter_data[norm_] = {"relax_factor": runtime_config.get("relax_factor", 0.35)}
                updated = True

        if updated:
            save_json_file(filter_path, filter_data)
            log("[FilterAdapt] Initialized relax_factor for new symbols", level="INFO")
    except Exception as e:
        log(f"[FilterAdapt] Error: {e}", level="ERROR")

    # Отчёт о финальном выборе
    log(f"Selected {len(active_symbols)} active symbols: {active_symbols}", level="INFO")

    try:
        os.makedirs(os.path.dirname(SYMBOLS_FILE), exist_ok=True)
        with symbols_file_lock, open(SYMBOLS_FILE, "w") as f:
            json.dump(active_symbols, f)
        log(f"Saved active symbols to {SYMBOLS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving active symbols: {e}", level="ERROR")

    # Telegram summary
    msg = (
        f"🔄 Symbol rotation:\n"
        f"Total active: {len(active_symbols)}\n"
        f"Balance: {balance:.1f} USDC\n"
        f"Volatility: {market_volatility:.2f}\n"
        f"Fixed: {len(fixed)} | Dynamic: {len(selected_dyn)}"
    )
    if balance < 300 and priority_pairs:
        prio_in_sel = [p for p in priority_pairs if p in active_symbols]
        if prio_in_sel:
            msg += f"\nPriority: {', '.join(prio_in_sel)}"

    send_telegram_message(msg, force=True)
    return active_symbols


def get_pair_limits():
    config = get_runtime_config()
    min_dyn = config.get("min_dynamic_pairs", 8)
    max_dyn = config.get("max_dynamic_pairs", 15)
    return min_dyn, max_dyn


def get_adaptive_filter_thresholds(current_candidates, target_minimum):
    """
    Adaptively adjust filter thresholds if not enough pairs pass

    Args:
        current_candidates: Number of pairs currently available for filtering
        target_minimum: Minimum required pairs

    Returns:
        dict: Adaptive thresholds for filtering
    """
    runtime_config = get_runtime_config()

    base_thresholds = {"min_atr_percent": runtime_config.get("atr_threshold_percent", 1.5) / 100, "min_volume_usdc": runtime_config.get("volume_threshold_usdc", 2000)}

    # If we have fewer candidates than needed, relax thresholds
    if current_candidates < target_minimum:
        relax_factor = 0.2  # Сделать фильтры ещё мягче
        base_thresholds["min_atr_percent"] *= relax_factor
        base_thresholds["min_volume_usdc"] *= relax_factor

        # Гарантируем, что фильтры не станут слишком малы
        base_thresholds["min_atr_percent"] = max(base_thresholds["min_atr_percent"], 0.002)
        base_thresholds["min_volume_usdc"] = max(base_thresholds["min_volume_usdc"], 250)

        log(
            f"⚠️ Only {current_candidates} candidates for {target_minimum} target. "
            f"Relaxing thresholds: ATR={base_thresholds['min_atr_percent'] * 100:.2f}%, "
            f"Vol={base_thresholds['min_volume_usdc']:.0f} USDC",
            level="WARNING",
        )

    return base_thresholds


def get_update_interval():
    """
    Determine the optimal symbol rotation interval based on:
    1. Account size
    2. Market volatility
    3. Trading hours
    """
    balance = get_cached_balance()
    base_interval = BASE_UPDATE_INTERVAL

    # Adjust for account size
    if balance < 120:
        account_factor = 0.75  # 25% быстрее для маленьких счетов
    elif balance < 200:
        account_factor = 0.9  # 10% быстрее для средних счетов
    else:
        account_factor = 1.0

    # Adjust for trading hours
    hour_factor = 0.75 if is_optimal_trading_hour() else 1.0

    # Adjust for market volatility
    market_volatility = get_market_volatility_index()
    if market_volatility > 1.5:
        volatility_factor = 0.7  # 30% быстрее при высокой волатильности
    elif market_volatility > 1.2:
        volatility_factor = 0.85  # 15% быстрее при средней волатильности
    else:
        volatility_factor = 1.0

    # Ensure minimum interval from config
    final_interval = max(PAIR_ROTATION_MIN_INTERVAL, int(base_interval * account_factor * hour_factor * volatility_factor))
    return final_interval


def start_symbol_rotation(stop_event):
    """
    Start periodic symbol rotation with adaptive interval.
    """
    while not stop_event.is_set():
        try:
            # Get the adaptive update interval
            update_interval = get_update_interval()

            # Perform symbol rotation
            select_active_symbols()

            # Sleep for the dynamic interval
            log(f"Next symbol rotation in {update_interval/60:.1f} minutes", level="DEBUG")

            # Sleep in smaller increments to respond faster to stop events
            sleep_interval = 10  # seconds
            for _ in range(int(update_interval / sleep_interval)):
                if stop_event.is_set():
                    break
                time.sleep(sleep_interval)

        except Exception as e:
            log(f"Symbol rotation error: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Symbol rotation failed: {e}", force=True)
            time.sleep(60)  # Short delay before retry on error


missed_opportunities = {}


def track_missed_opportunities():
    """Track pairs that were missed but performed well."""
    global missed_opportunities

    all_pairs = fetch_all_symbols()

    active_pairs = []
    if os.path.exists(SYMBOLS_FILE):
        with symbols_file_lock, open(SYMBOLS_FILE, "r") as f:
            active_pairs = json.load(f)

    missed_opportunities = {}
    missed_logs = []  # Новый список для аккуратного сбора логов

    for pair in all_pairs:
        if pair in active_pairs:
            continue

        df = fetch_symbol_data(pair, timeframe="15m", limit=96)
        if df is None or len(df) < 20:
            continue

        price_24h_ago = df["close"].iloc[0]
        price_now = df["close"].iloc[-1]
        potential_profit = ((price_now - price_24h_ago) / price_24h_ago) * 100

        if abs(potential_profit) > 5:
            metrics = calculate_short_term_metrics(df)
            atr_vol = calculate_atr_volatility(df)
            avg_volume = df["volume"].mean()

            missed_opportunities[pair] = {
                "count": missed_opportunities.get(pair, {}).get("count", 0) + 1,
                "profit": missed_opportunities.get(pair, {}).get("profit", 0) + potential_profit,
                "momentum": metrics.get("momentum", 0),
                "atr_volatility": atr_vol,
                "avg_volume": avg_volume,
            }

            if abs(potential_profit) > 10:
                # Вместо логирования сразу — добавляем в список
                missed_logs.append(f"- {pair} ({potential_profit:.2f}% profit, Momentum: {metrics.get('momentum', 0):.2f}%, " f"ATR vol: {atr_vol:.4f}, Avg volume: {avg_volume:,.0f})")

    # Групповое логирование одним сообщением
    if missed_logs:
        log("[Missed Opportunities]\n" + "\n".join(missed_logs), level="WARNING")

    # Сохраняем файл
    try:
        with open(MISSED_OPPORTUNITIES_FILE, "w") as f:
            json.dump(missed_opportunities, f, indent=2)
        log(f"Saved missed opportunities to {MISSED_OPPORTUNITIES_FILE}", level="INFO")
    except Exception as e:
        log(f"Error saving missed opportunities: {e}", level="ERROR")
