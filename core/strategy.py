# strategy.py

import json
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd
import ta

from common.config_loader import (
    DRY_RUN,
    MIN_NOTIONAL_OPEN,
    TAKER_FEE_RATE,
    TRADING_HOURS_FILTER,
)
from core.binance_api import fetch_ohlcv
from core.component_tracker import log_component_data
from core.entry_logger import log_entry
from core.missed_signal_logger import log_missed_signal
from core.risk_utils import get_adaptive_risk_percent

# Импорт из signal_utils
from core.signal_utils import (
    detect_ema_crossover,
    detect_volume_spike,
    get_signal_breakdown,
    passes_1plus1,
)
from core.tp_utils import calculate_tp_levels
from core.trade_engine import calculate_position_size, trade_manager
from telegram.telegram_utils import send_telegram_message
from utils_core import (
    get_cached_balance,
    get_runtime_config,
    is_optimal_trading_hour,
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
    import ta  # Импорт только для этой функции

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
    Минимальные фильтры: rsi_15m > порога, rel_volume_15m > порога, atr_15m > 0.
    """
    try:
        config = get_runtime_config()
        rsi_thr = config.get("rsi_threshold", 50)
        vol_thr = config.get("rel_volume_threshold", 0.5)

        latest = df.iloc[-1]

        if latest.get("rsi_15m", 0) < rsi_thr:
            log(f"[Filter] {symbol} ❌ rsi_15m < {rsi_thr}", level="DEBUG")
            return False

        if latest.get("rel_volume_15m", 0) < vol_thr:
            log(f"[Filter] {symbol} ❌ rel_volume_15m < {vol_thr}", level="DEBUG")
            return False

        if latest.get("atr_15m", 0) <= 0:
            log(f"[Filter] {symbol} ❌ atr_15m <= 0", level="DEBUG")
            return False

        return True

    except Exception as e:
        log(f"[Filter] {symbol} error: {e}", level="ERROR")
        return False


def should_enter_trade(symbol, exchange, last_trade_times, last_trade_times_lock):
    """
    Основная функция проверки входа и генерации сигнала для enter_trade(...).
    Возвращает (signal_tuple, failure_reasons),
    где:
      - signal_tuple = (direction, qty, is_reentry, breakdown) или None
      - failure_reasons = list строк с причинами отказа

    Пример использования:
      buy_signal, buy_failures = should_enter_trade(...)
      if buy_signal is None:
          # отказ, buy_failures содержит причины
      else:
          direction, qty, is_reentry, breakdown = buy_signal
          # идём дальше
    """

    # Если symbol пришёл в виде словаря
    if isinstance(symbol, dict):
        symbol = symbol.get("symbol", "")

    symbol = normalize_symbol(symbol)
    failure_reasons = []

    log(f"[Entry] Checking {symbol} for entry...", level="DEBUG")

    # Если нужно определять пару (fixed / dynamic)
    pair_type = symbol_type_map.get(symbol, "unknown")

    # 1) Данные
    df = fetch_data_multiframe(symbol)
    if df is None:
        failure_reasons.append("data_fetch_error")
        log_missed_signal(symbol, 0, {}, reason="data_fetch_error")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    if not isinstance(df, pd.DataFrame):
        log(f"[Reject] {symbol} => fetch_data_multiframe returned {type(df).__name__}", level="ERROR")
        return None, ["data_format_error"]

    # 2) Проверка торговых часов (опционально)
    if TRADING_HOURS_FILTER and not is_optimal_trading_hour():
        failure_reasons.append("non_optimal_hours")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    # 3) Фильтры
    if not passes_filters(df, symbol):
        failure_reasons.append("filter_fail")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    # 4) Сигнал "1+1"
    breakdown = get_signal_breakdown(df)
    if not breakdown:
        failure_reasons.append("no_breakdown")
        log_missed_signal(symbol, {}, reason="no_breakdown")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    if not passes_1plus1(breakdown):
        failure_reasons.append("missing_1plus1")
        log_missed_signal(symbol, breakdown, reason="missing_1plus1")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    # Лог компонентов
    log(f"[1+1] {symbol} breakdown={breakdown}, passes=True", level="DEBUG")
    log_component_data(symbol, breakdown, is_successful=True)

    # 5) Определяем BUY/SELL, например по macd_5m
    macd_val = df["macd_5m"].iloc[-1]
    macd_sig = df["macd_signal_5m"].iloc[-1]
    direction = "BUY" if macd_val > macd_sig else "SELL"

    # 6) Расчёт qty (псевдо)
    entry_price = df["close"].iloc[-1]
    atr_series = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range()
    atr = atr_series.iloc[-1] if len(atr_series) else 0.0

    atr_multiplier = 1.5
    sl_distance = atr * atr_multiplier
    stop_price = entry_price - sl_distance if direction == "BUY" else entry_price + sl_distance

    balance = get_cached_balance()
    risk_percent = get_adaptive_risk_percent(balance)
    qty = calculate_position_size(entry_price, stop_price, balance * risk_percent, symbol=symbol)

    # На случай если qty=0
    if not qty:
        qty = MIN_NOTIONAL_OPEN / entry_price  # fallback

    notional = qty * entry_price

    # Быстрая проверка комиссии и потенциала
    commission = 2 * (qty * entry_price * TAKER_FEE_RATE)
    net_check = (qty * abs(entry_price * 0.01)) - commission
    if net_check <= 0:
        failure_reasons.append("insufficient_profit")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    # TP/SL расчёт
    tp1, tp2, sl_price, share1, share2 = calculate_tp_levels(entry_price, direction, df=df)
    if not tp1 or not sl_price:
        failure_reasons.append("invalid_tp_sl")
        log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
        return None, failure_reasons

    # 7) Кулдаун
    with last_trade_times_lock:
        now_ts = datetime.utcnow().timestamp()
        last_t = last_trade_times.get(symbol)
        cooldown_sec = get_runtime_config().get("cooldown_minutes", 30) * 60
        if last_t and (now_ts - last_t.timestamp()) < cooldown_sec:
            failure_reasons.append("cooldown_active")
            log(f"[Reject] {symbol} => {failure_reasons}", level="DEBUG")
            return None, failure_reasons
        last_trade_times[symbol] = datetime.utcnow()

    # 8) Логируем успех (entry_log) и Telegram
    entry_data = {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "qty": qty,
        "notional": round(notional, 2),
        "breakdown": breakdown,
        "pair_type": pair_type,
        "atr": round(atr, 5),
        "sl": round(stop_price, 5),
    }
    log_entry(entry_data, status="SUCCESS", mode="DRY_RUN" if DRY_RUN else "REAL_RUN")

    if DRY_RUN:
        send_telegram_message(f"🧪 DRY_RUN {symbol} ({pair_type}) {direction} qty={qty:.3f}", force=True)
    else:
        send_telegram_message(f"🚀 OPEN {symbol} ({pair_type}) {direction} qty={qty:.3f}", force=True)

    # Пример логики re-entry
    is_reentry = False

    # ✔ Возвращаем успех:
    # ( (direction, qty, is_reentry, breakdown), [] )
    return (direction, qty, is_reentry, breakdown), []


def calculate_tp_targets():
    """
    Пример функции расчёта TP (если нужно где-то в отчётах).
    """
    try:
        positions = trade_manager._trades  # или exchange.fetch_positions()
        results = []
        for symbol, data in positions.items():
            entry_price = data.get("entry", 0)
            if entry_price > 0:
                # Пример: +5% от цены
                tp_price = entry_price * 1.05
                results.append({"symbol": symbol, "tp_price": tp_price})
                log(f"[TP] {symbol} => {tp_price}", level="DEBUG")
        return results

    except Exception as e:
        log(f"[calculate_tp_targets] Ошибка: {e}", level="ERROR")
        return []
