# strategy.py

import json
import threading
from pathlib import Path

import pandas as pd
import ta

from core.binance_api import fetch_ohlcv

# Импорт из signal_utils
from core.signal_utils import (
    detect_ema_crossover,
    detect_volume_spike,
)
from core.trade_engine import trade_manager
from utils_core import (
    get_runtime_config,
    normalize_symbol,
)
from utils_logging import log

# Глобальный трекинг времени последней сделки
last_trade_times = {}
last_trade_times_lock = threading.Lock()

# Файл с активными символами (содержит {"symbol": "...", "type": "fixed"/"dynamic", ...})
SYMBOLS_FILE = "data/dynamic_symbols.json"


def load_symbol_type_map():
    """
    Загружаем файл с описанием пар (fixed/dynamic и т.п.),
    возвращаем словарь вида {"BTC/USDC:USDC": "fixed", ...}
    """
    try:
        with open(SYMBOLS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        info_dict = {}
        for item in data:
            # normalize_symbol для единообразия
            s = normalize_symbol(item.get("symbol", ""))
            info_dict[s] = item.get("type", "unknown")
        return info_dict
    except Exception as e:
        log(f"[strategy] Failed to load symbol info: {e}", level="ERROR")
        return {}


# Заранее загружаем type-карту
symbol_type_map = load_symbol_type_map()


def fetch_data_multiframe(symbol):
    """
    Загружаем OHLCV по 3m, 5m, 15m. Считаем RSI, MACD, ATR, volume_spike и т. д.
    Возвращаем общий df или None при ошибке.
    """

    try:
        tf_map = {"3m": 300, "5m": 300, "15m": 300}
        frames = {}
        fetch_debug = {}

        for tf, limit in tf_map.items():
            raw = fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            if not raw or len(raw) < 30:
                log(f"[fetch_data_multiframe] {symbol}: недостаточно данных {tf}", level="WARNING")
                return None

            df_tf = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
            df_tf["time"] = pd.to_datetime(df_tf["time"], unit="ms")
            df_tf.set_index("time", inplace=True)
            frames[tf] = df_tf

        # Индикаторы на 3m
        df_3m = frames["3m"].copy()
        df_3m["ema_3m"] = ta.trend.EMAIndicator(df_3m["close"], 21).ema_indicator()
        df_3m["rsi_3m"] = ta.momentum.RSIIndicator(df_3m["close"], 9).rsi()

        # Индикаторы на 5m
        df_5m = frames["5m"].copy()
        df_5m["rsi_5m"] = ta.momentum.RSIIndicator(df_5m["close"], 14).rsi()
        macd_5m = ta.trend.MACD(df_5m["close"])
        df_5m["macd_5m"] = macd_5m.macd()
        df_5m["macd_signal_5m"] = macd_5m.macd_signal()

        # Индикаторы на 15m
        df_15m = frames["15m"].copy()
        df_15m["rsi_15m"] = ta.momentum.RSIIndicator(df_15m["close"], 14).rsi()
        df_15m["atr_15m"] = ta.volatility.AverageTrueRange(df_15m["high"], df_15m["low"], df_15m["close"], 14).average_true_range()
        df_15m["volume_ma_15m"] = df_15m["volume"].rolling(20).mean()
        df_15m["rel_volume_15m"] = df_15m["volume"] / df_15m["volume_ma_15m"]

        # Объединяем в один DataFrame
        df = df_3m.join(df_5m, rsuffix="_5m").join(df_15m, rsuffix="_15m").dropna().reset_index()

        # Общая ATR
        df["atr"] = df["atr_15m"]

        # Определяем EMA‐пересечение
        has_cross, _dir = detect_ema_crossover(df)
        df["ema_cross"] = has_cross

        # Price Action (крупная свеча)
        df["candle_size"] = (df["close"] - df["open"]).abs()
        df["avg_candle_size"] = df["candle_size"].rolling(20).mean()
        df["price_action"] = df["candle_size"] > (df["avg_candle_size"] * 1.5)

        # Volume spike
        vol_spike = detect_volume_spike(df)
        df["volume_spike"] = False
        if len(df) > 0:
            df.loc[df.index[-1], "volume_spike"] = vol_spike

        fetch_debug[f"{symbol}_final_shape"] = df.shape

        # Сохраняем отладочные данные (опц.)
        Path("data").mkdir(exist_ok=True)
        with open("data/fetch_debug.json", "w", encoding="utf-8") as f:
            json.dump(fetch_debug, f, indent=2)

        return df

    except Exception as e:
        log(f"[fetch_data_multiframe] {symbol} error: {e}", level="ERROR")
        return None


def passes_filters(df: pd.DataFrame, symbol: str) -> bool:
    """
    Фильтры по RSI, относительному и абсолютному объёму, ATR%:
    - rsi_15m >= threshold
    - rel_volume_15m >= threshold
    - atr_15m / price >= atr_threshold_percent
    - volume_usdt >= volume_threshold_usdc
    """
    try:
        config = get_runtime_config()
        rsi_thr = config.get("rsi_threshold", 50)
        vol_thr = config.get("rel_volume_threshold", 0.3)
        atr_thr_pct = config.get("atr_threshold_percent", 0.0015)
        vol_abs_min = config.get("volume_threshold_usdc", 600)

        latest = df.iloc[-1]
        close = latest.get("close", 0)
        atr = latest.get("atr_15m", 0)
        atr_pct = atr / close if close > 0 else 0
        rel_volume = latest.get("rel_volume_15m", 0)
        volume_usdt = latest.get("volume_usdt_15m", 0)

        if latest.get("rsi_15m", 0) < rsi_thr:
            log(f"[Filter] {symbol} ❌ rsi_15m < {rsi_thr}", level="DEBUG")
            return False

        if rel_volume < vol_thr:
            log(f"[Filter] {symbol} ❌ rel_volume_15m < {vol_thr}", level="DEBUG")
            return False

        if atr_pct < atr_thr_pct:
            log(f"[Filter] {symbol} ❌ atr_pct {atr_pct:.5f} < {atr_thr_pct}", level="DEBUG")
            return False

        if volume_usdt < vol_abs_min:
            log(f"[Filter] {symbol} ❌ volume_usdt {volume_usdt:.1f} < {vol_abs_min}", level="DEBUG")
            return False

        return True

    except Exception as e:
        log(f"[Filter] {symbol} error: {e}", level="ERROR")
        return False


def should_enter_trade(symbol, last_trade_times, last_trade_times_lock):
    """
    Генерирует сигнал на вход в сделку.
    Возвращает: (direction, qty, is_reentry, breakdown), либо None + причины отказа.
    """
    from datetime import datetime

    import numpy as np
    import pandas as pd
    import ta

    from common.config_loader import MIN_NOTIONAL_OPEN, TAKER_FEE_RATE, is_monitoring_hours_utc
    from core.component_tracker import log_component_data
    from core.entry_logger import log_entry
    from core.missed_signal_logger import log_missed_signal
    from core.position_manager import check_entry_allowed
    from core.runtime_state import is_symbol_paused, is_trading_globally_paused, pause_all_trading
    from core.signal_utils import get_signal_breakdown, passes_1plus1
    from core.strategy import fetch_data_multiframe, symbol_type_map
    from core.tp_utils import calculate_tp_levels, check_min_profit
    from core.trade_engine import calculate_position_size, calculate_risk_amount
    from open_interest_tracker import fetch_open_interest
    from tp_logger import get_today_pnl_from_csv
    from utils_core import get_cached_balance, get_runtime_config, normalize_symbol
    from utils_logging import log

    symbol = normalize_symbol(symbol)
    failure_reasons = []

    log(f"[SignalCheck] 🟢 Evaluating {symbol}", level="DEBUG")

    try:
        if get_today_pnl_from_csv() < -5.0:
            pause_all_trading(minutes=60)
    except Exception as e:
        log(f"[WARN] Could not evaluate daily PnL: {e}", level="WARNING")

    if is_trading_globally_paused():
        failure_reasons.append("daily_loss_limit")
        return None, failure_reasons
    if is_symbol_paused(symbol):
        failure_reasons.append("symbol_paused")
        return None, failure_reasons

    log(f"[Entry] Checking {symbol} for entry...", level="DEBUG")

    pair_type = symbol_type_map.get(symbol, "unknown")
    df = fetch_data_multiframe(symbol)
    if df is None or not isinstance(df, pd.DataFrame):
        failure_reasons.append("data_fetch_error")
        log_missed_signal(symbol, {}, reason="data_fetch_error")
        return None, failure_reasons

    direction, breakdown = get_signal_breakdown(df)

    # 💬 DEBUG LOG
    log(f"[SignalCheck] Breakdown for {symbol}: {breakdown}", level="DEBUG")
    log(f"[SignalCheck] Direction={direction}", level="DEBUG")

    if not direction or not breakdown:
        failure_reasons.append("no_direction")
        log_missed_signal(symbol, {}, reason="no_direction")
        return None, failure_reasons

    if not passes_1plus1(breakdown):
        failure_reasons.append("missing_1plus1")
        log_missed_signal(symbol, breakdown, reason="missing_1plus1")
        return None, failure_reasons

    log_component_data(symbol, breakdown, is_successful=True)

    try:
        open_interest = fetch_open_interest(symbol)
        breakdown["open_interest"] = round(open_interest, 2)
    except Exception as e:
        log(f"[OI] Failed to fetch open_interest for {symbol}: {e}", level="WARNING")
        breakdown["open_interest"] = 0.0

    try:
        entry_price = df["close"].iloc[-1]
        if pd.isna(entry_price) or entry_price <= 0:
            raise ValueError("entry_price invalid")
    except Exception:
        failure_reasons.append("entry_error")
        log_missed_signal(symbol, breakdown, reason="entry_error")
        return None, failure_reasons

    atr_series = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()
    atr = atr_series.iloc[-1] if len(atr_series) else 0.0
    atr_pct = atr / entry_price if entry_price > 0 else 0

    balance = get_cached_balance()
    log(f"[DEBUG] Capital pre-check: balance={balance:.2f}", level="DEBUG")

    can_enter, reason = check_entry_allowed(balance)
    if not can_enter:
        failure_reasons.append(reason)
        log_missed_signal(symbol, breakdown, reason=reason)
        return None, failure_reasons

    volume = breakdown.get("volume", 0)

    # ✅ Новый: рассчитываем риск и adaptive SL
    risk_amount, effective_sl = calculate_risk_amount(balance, symbol=symbol, atr_percent=atr_pct, volume_usdc=volume)
    stop_price = entry_price * (1 - effective_sl) if direction == "buy" else entry_price * (1 + effective_sl)

    qty = calculate_position_size(entry_price, stop_price, risk_amount, symbol=symbol, balance=balance)
    if not qty or qty <= 0:
        fallback_qty = MIN_NOTIONAL_OPEN / entry_price
        log(f"[Fallback] {symbol} qty fallback: {fallback_qty:.4f}", level="DEBUG")
        qty = fallback_qty

    notional = qty * entry_price

    try:
        tp1, tp2, sl_price, share1, share2 = calculate_tp_levels(entry_price, direction, df=df)
        if any(x is None or (isinstance(x, float) and np.isnan(x)) for x in (tp1, sl_price, share1)):
            raise ValueError("TP/SL invalid")

        log(f"[TP_LEVELS] {symbol} → TP1={tp1:.5f}, TP2={tp2:.5f}, SL={sl_price:.5f}, share1={share1}, share2={share2}", level="DEBUG")

        min_profit_required = get_runtime_config().get("min_profit_threshold", 0.06)
        enough_profit, net_profit = check_min_profit(entry_price, tp1, qty, share1, direction, TAKER_FEE_RATE, min_profit_required)

        log(f"[ProfitCalc] {symbol} → NetProfit=${net_profit:.2f} (required=${min_profit_required:.2f})", level="DEBUG")

        if not enough_profit:
            failure_reasons.append("insufficient_profit")
            log_missed_signal(symbol, breakdown, reason="insufficient_profit")
            return None, failure_reasons

    except Exception:
        failure_reasons.append("invalid_tp_sl")
        log_missed_signal(symbol, breakdown, reason="invalid_tp_sl")
        return None, failure_reasons

    cfg = get_runtime_config()
    with last_trade_times_lock:
        now_ts = datetime.utcnow().timestamp()
        last_t = last_trade_times.get(symbol)
        cooldown_sec = cfg.get("cooldown_minutes", 5) * 60
        if last_t and (now_ts - last_t.timestamp()) < cooldown_sec:
            failure_reasons.append("cooldown_active")
            log_missed_signal(symbol, breakdown, reason="cooldown_active")
            return None, failure_reasons
        last_trade_times[symbol] = datetime.utcnow()

    is_reentry = breakdown.get("is_reentry", False)
    if is_monitoring_hours_utc():
        score = breakdown.get("score", 0)
        if not is_reentry and score < 8.5:
            failure_reasons.append("monitoring_hours")
            log(f"[TimeFilter] ⏰ {symbol} skipped in monitoring hours (score={score})", level="DEBUG")
            log_missed_signal(symbol, breakdown, reason="monitoring_hours")
            return None, failure_reasons

    entry_data = {
        "symbol": symbol,
        "direction": direction,
        "entry": entry_price,
        "qty": qty,
        "notional": round(notional, 2),
        "breakdown": breakdown,
        "pair_type": pair_type,
        "atr": round(atr, 5),
        "sl": round(sl_price, 5),
    }

    try:
        log_entry(entry_data, status="SUCCESS")
    except Exception as e:
        log(f"[WARN] Failed to log_entry for {symbol}: {e}", level="WARNING")

    # ✅ Проверка структуры выхода
    try:
        assert direction in ("buy", "sell")
        assert isinstance(qty, (float, int)) and qty > 0
        assert isinstance(breakdown, dict)
    except Exception as e:
        failure_reasons.append("invalid_return_structure")
        log(f"[SignalCheck] ❌ {symbol} → return structure invalid: {e}", level="ERROR")
        log_missed_signal(symbol, breakdown, reason="invalid_return_structure")
        return None, failure_reasons

    # ✅ Явный лог успешного прохода
    log(f"[SignalCheck] ✅ Passed {symbol} | direction={direction} qty={qty:.4f}", level="INFO")
    return (direction, qty, is_reentry, breakdown), []


def calculate_tp_targets():
    """
    Возвращает текущие TP цели по активным сделкам (по tp1_price, fallback = +5%)
    """
    try:
        positions = trade_manager._trades
        results = []

        for symbol, data in positions.items():
            entry_price = data.get("entry", 0)
            if not entry_price or entry_price <= 0:
                continue

            tp_price = data.get("tp1_price") or entry_price * 1.05
            if tp_price > 0:
                result = {"symbol": symbol, "tp_price": round(tp_price, 4), "entry": round(entry_price, 4), "pair_type": data.get("pair_type", "unknown")}
                results.append(result)
                log(f"[TP-Target] {symbol} → TP1: {tp_price:.4f}", level="DEBUG")

        return results

    except Exception as e:
        log(f"[calculate_tp_targets] Ошибка: {e}", level="ERROR")
        return []
