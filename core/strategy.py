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
                log(f"[fetch_data_multiframe] {symbol} ❌ returning None due to insufficient TF data", level="WARNING")
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
        df_15m["volume_usdt_15m"] = df_15m["volume"] * df_15m["close"]

        # Объединяем
        df = df_3m.join(df_5m, rsuffix="_5m").join(df_15m, rsuffix="_15m").dropna().reset_index()

        if df.empty:
            log(f"[fetch_data_multiframe] {symbol} ❌ Final dataframe empty after merge/join", level="WARNING")
            return None

        df["atr"] = df["atr_15m"]

        # EMA cross
        has_cross, _dir = detect_ema_crossover(df)
        df["ema_cross"] = has_cross

        # Price Action
        df["candle_size"] = (df["close"] - df["open"]).abs()
        df["avg_candle_size"] = df["candle_size"].rolling(20).mean()
        df["price_action"] = df["candle_size"] > (df["avg_candle_size"] * 1.5)

        # Volume spike
        vol_spike = detect_volume_spike(df)
        df["volume_spike"] = False
        if len(df) > 0:
            df.loc[df.index[-1], "volume_spike"] = vol_spike

        fetch_debug[f"{symbol}_final_shape"] = df.shape

        # Отладка
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
    from datetime import datetime, timedelta

    import numpy as np
    import pandas as pd
    import ta

    from common.config_loader import MIN_NOTIONAL_OPEN, TAKER_FEE_RATE
    from common.leverage_config import get_leverage_for_symbol
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

    pair_type = symbol_type_map.get(symbol, "unknown")
    df = fetch_data_multiframe(symbol)
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        failure_reasons.append("fetch_data_empty")
        log(f"[DataFetch] ❌ Empty or invalid dataframe for {symbol}", level="WARNING")
        log_missed_signal(symbol, {}, reason="fetch_data_empty")
        return None, failure_reasons

    cfg = get_runtime_config()
    require_closed = cfg.get("require_closed_candle_for_entry", False)
    if require_closed:
        now = datetime.utcnow()
        latest_time = df.iloc[-1]["time"] if "time" in df.columns else None
        if latest_time and now - latest_time < timedelta(minutes=1):
            failure_reasons.append("candle_not_closed")
            log_missed_signal(symbol, {}, reason="candle_not_closed")
            return None, failure_reasons

    direction, breakdown = get_signal_breakdown(df)
    if not direction or not breakdown:
        failure_reasons.append("no_direction")
        log_missed_signal(symbol, {}, reason="no_direction")
        return None, failure_reasons

    breakdown["pair_type"] = pair_type

    # === Signal Score
    weights = cfg.get("signal_strength_weighting", {"MACD": 0.4, "RSI": 0.3, "EMA": 0.3})
    macd_strength = breakdown.get("macd_strength", 0.0)
    rsi_strength = breakdown.get("rsi_strength", 0.0)
    ema_score = float(breakdown.get("EMA_CROSS", 0))

    score = macd_strength * weights.get("MACD", 0.4) + rsi_strength * weights.get("RSI", 0.3) + ema_score * weights.get("EMA", 0.3)
    signal_score = round(score, 4)
    breakdown["signal_score"] = signal_score
    log(f"[Score] {symbol} → signal_score={signal_score:.4f}", level="DEBUG")

    min_macd_strength = cfg.get("min_macd_strength", 0.002)
    min_rsi_strength = cfg.get("min_rsi_strength", 12.0)

    enable_override = cfg.get("enable_strong_signal_override", False)
    macd_override = cfg.get("macd_strength_override", 1.0)
    rsi_override = cfg.get("rsi_strength_override", 10.0)

    if macd_strength < min_macd_strength and rsi_strength < min_rsi_strength:
        if enable_override and (macd_strength >= macd_override or rsi_strength >= rsi_override):
            log(f"[Override] ✅ Signal override triggered: macd={macd_strength}, rsi={rsi_strength}", level="INFO")
        else:
            failure_reasons.append("weak_macd_rsi")
            log_missed_signal(symbol, breakdown, reason="weak_macd_rsi")
            return None, failure_reasons

    htf_score = breakdown.get("HTF", 1)
    if direction == "sell" and htf_score < 1 and not cfg.get("allow_short_if_htf_zero", True):
        failure_reasons.append("htf_mismatch")
        log_missed_signal(symbol, breakdown, reason="htf_mismatch")
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
    can_enter, reason = check_entry_allowed(balance)
    if not can_enter:
        failure_reasons.append(reason)
        log_missed_signal(symbol, breakdown, reason=reason)
        return None, failure_reasons

    volume = breakdown.get("volume", 0)
    risk_amount, effective_sl = calculate_risk_amount(balance, symbol=symbol, atr_percent=atr_pct, volume_usdc=volume)

    leverage = get_leverage_for_symbol(symbol)
    qty, _ = calculate_position_size(symbol, entry_price, balance, leverage)

    if qty is None or qty <= 0:
        failure_reasons.append("qty_zero_or_invalid")
        log(f"[REJECTED] {symbol}: qty is {qty}, invalid for entry", level="WARNING")
        log_missed_signal(symbol, breakdown, reason="qty_zero_or_invalid")
        return None, failure_reasons

    notional = qty * entry_price
    if notional < MIN_NOTIONAL_OPEN:
        log(f"[NotionalCheck] {symbol}: notional={notional:.4f} < MIN_NOTIONAL_OPEN={MIN_NOTIONAL_OPEN}", level="WARNING")
        failure_reasons.append("notional_too_small")
        log_missed_signal(symbol, breakdown, reason="notional_too_small")
        return None, failure_reasons

    try:
        tp1, tp2, sl_price, share1, share2, tp3_share = calculate_tp_levels(entry_price, direction, df=df)
        if any(x is None or (isinstance(x, float) and np.isnan(x)) for x in (tp1, sl_price, share1)):
            raise ValueError("TP/SL invalid")

        tp_prices = [tp1, tp2, tp2 * 1.5]
        breakdown["tp1"] = tp1
        breakdown["tp2"] = tp2
        breakdown["sl_price"] = sl_price
        breakdown["tp1_share"] = share1
        breakdown["tp2_share"] = share2
        breakdown["tp3_share"] = tp3_share
        breakdown["tp_prices"] = tp_prices
        breakdown["tp_total_qty"] = round(share1 + share2 + tp3_share, 3)

        min_profit_required = cfg.get("min_profit_threshold", 0.06)
        enough_profit, net_profit = check_min_profit(entry_price, tp1, qty, share1, direction, TAKER_FEE_RATE, min_profit_required)

        log(f"[TP_LEVELS] {symbol} → TP1={tp1:.5f}, TP2={tp2:.5f}, SL={sl_price:.5f}, share1={share1}, share2={share2}", level="DEBUG")
        log(f"[ProfitCalc] {symbol} → NetProfit=${net_profit:.2f} (required=${min_profit_required:.2f})", level="DEBUG")

        if not enough_profit:
            failure_reasons.append("insufficient_profit")
            log_missed_signal(symbol, breakdown, reason="insufficient_profit")
            return None, failure_reasons

    except Exception:
        failure_reasons.append("invalid_tp_sl")
        log_missed_signal(symbol, breakdown, reason="invalid_tp_sl")
        return None, failure_reasons

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
        "tp_prices": tp_prices,
        "tp1": tp1,
        "tp2": tp2,
        "share1": share1,
        "share2": share2,
    }

    try:
        log_entry(entry_data, status="SUCCESS")
    except Exception as e:
        log(f"[WARN] Failed to log_entry for {symbol}: {e}", level="WARNING")

    try:
        assert direction in ("buy", "sell")
        assert isinstance(qty, (float, int)) and qty > 0
        assert isinstance(breakdown, dict)
    except Exception:
        failure_reasons.append("invalid_return_structure")
        log_missed_signal(symbol, breakdown, reason="invalid_return_structure")
        return None, failure_reasons

    log(f"[SignalCheck] ✅ Passed {symbol} | direction={direction} qty={qty:.4f}", level="INFO")
    return (direction, qty, is_reentry, breakdown), []


def calculate_tp_targets():
    """
    Возвращает текущие TP/SL цели по активным сделкам:
    - tp1_price, tp2_price, tp3_price, sl_price
    - fallback при отсутствии TP
    - добавлены tp_total_qty и tp_fallback_used
    """
    from core.trade_engine import trade_manager
    from utils_logging import log

    try:
        positions = trade_manager.get_all_trades()
        results = []

        for symbol, data in positions.items():
            if data.get("closed_logged"):
                continue

            entry_price = data.get("entry", 0)
            if not entry_price or entry_price <= 0:
                continue

            tp1 = data.get("tp1_price") or round(entry_price * 1.05, 4)
            tp2 = data.get("tp2_price") or round(entry_price * 1.10, 4)
            tp3 = data.get("tp3_price") or round(tp2 * 1.5, 4)
            sl_price = data.get("sl_price") or round(entry_price * 0.985, 4)

            tp_total_qty = round(data.get("tp_total_qty", 0.0), 6)
            fallback_used = bool(data.get("tp_fallback_used", False))

            result = {
                "symbol": symbol,
                "entry": round(entry_price, 4),
                "tp1": round(tp1, 4),
                "tp2": round(tp2, 4),
                "tp3": round(tp3, 4),
                "sl": round(sl_price, 4),
                "tp_total_qty": tp_total_qty,
                "fallback": fallback_used,
                "pair_type": data.get("pair_type", "unknown"),
            }
            results.append(result)

            log(f"[TP-Target] {symbol} → TP1={tp1:.4f}, TP2={tp2:.4f}, TP3={tp3:.4f}, SL={sl_price:.4f}, fallback={fallback_used}", level="DEBUG")

        return results

    except Exception as e:
        log(f"[calculate_tp_targets] Ошибка: {e}", level="ERROR")
        return []
