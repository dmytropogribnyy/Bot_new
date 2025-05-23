# strategy.py

import threading
from datetime import datetime

import pandas as pd
import ta

# == Импорт основных констант и утилит ==
from common.config_loader import (
    BREAKOUT_DETECTION,
    TRADING_HOURS_FILTER,
)
from core.binance_api import fetch_ohlcv
from core.trade_engine import trade_manager
from utils_core import get_cached_balance, get_runtime_config, is_optimal_trading_hour
from utils_logging import log

# == Глобальные переменные для слежения за последними сделками ==
last_trade_times = {}
last_trade_times_lock = threading.Lock()

# ---------------------------------------------------------------------------
# 1) Вспомогательные методы для HTF, MultiFrame fetch и определения market regime
# ---------------------------------------------------------------------------


def fetch_htf_data(symbol, tf="1h"):
    """
    Загружает 1h‐свечи и считает пару индикаторов (EMA / momentum),
    используемых для get_htf_trend().
    """
    try:
        raw = fetch_ohlcv(symbol, timeframe=tf, limit=100)
        if not raw or len(raw) < 30:
            return None
        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)

        df["ema"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
        df["momentum"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        return df
    except Exception as e:
        log(f"[HTF] Error while fetching HTF data for {symbol}: {e}", level="ERROR")
        return None


def get_htf_trend(symbol, tf="1h"):
    """
    Определяем HTF‐тренд на заданном таймфрейме (по умолчанию 1h).
    Используется для USE_HTF_CONFIRMATION.
    """
    try:
        df_htf = fetch_htf_data(symbol, tf=tf)
        if df_htf is None or len(df_htf) < 3:
            return False

        price_above_ema = df_htf["close"].iloc[-1] > df_htf["ema"].iloc[-1]
        momentum_increasing = False
        if "momentum" in df_htf.columns:
            momentum_increasing = df_htf["momentum"].iloc[-1] > df_htf["momentum"].iloc[-2]

        return bool(price_above_ema and momentum_increasing)
    except Exception as e:
        log(f"Error in get_htf_trend for {symbol}: {e}", level="ERROR")
        return False


def detect_ema_crossover(df, fast_window=9, slow_window=21):
    """
    Определяет факт пересечения EMA (быстрой / медленной) на последних свечах.
    Возвращает (has_crossover: bool, direction: int),
    где direction=+1 — пересечение вверх, -1 — пересечение вниз, 0 — нет пересечения.
    """
    try:
        fast_ema = ta.trend.EMAIndicator(df["close"], window=fast_window).ema_indicator()
        slow_ema = ta.trend.EMAIndicator(df["close"], window=slow_window).ema_indicator()

        prev_fast = fast_ema.iloc[-2]
        prev_slow = slow_ema.iloc[-2]
        curr_fast = fast_ema.iloc[-1]
        curr_slow = slow_ema.iloc[-1]

        if prev_fast < prev_slow and curr_fast > curr_slow:
            return True, 1
        elif prev_fast > prev_slow and curr_fast < curr_slow:
            return True, -1
        else:
            return False, 0
    except Exception as e:
        log(f"Error in detect_ema_crossover: {e}", level="ERROR")
        return False, 0


def fetch_data_multiframe(symbol):
    """
    Загружает OHLCV по 3m, 5m, 15m и рассчитывает индикаторы.
    Возвращает df_final с нужными колонками (atr, rsi, macd, ...).
    Сохраняет отладочную инфу в data/fetch_debug.json.
    """
    import json
    from pathlib import Path

    import pandas as pd
    import ta

    from common.config_loader import USE_HTF_CONFIRMATION
    from core.binance_api import fetch_ohlcv
    from core.strategy import detect_ema_crossover, get_htf_trend
    from utils_logging import log

    tf_map = {"3m": 300, "5m": 300, "15m": 300}
    frames = {}
    fetch_debug = {}

    try:
        # 1) Получаем данные для каждого TF
        for tf, limit in tf_map.items():
            raw = fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            raw_len = len(raw) if raw else 0
            log(f"[MultiTF] {symbol} {tf} raw_len = {raw_len}", level="DEBUG")
            fetch_debug[f"{symbol}_{tf}"] = raw_len

            if raw_len < 30:
                log(f"[MultiTF] Insufficient {tf} data for {symbol} (raw_len={raw_len})", level="WARNING")
                return None

            df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df.set_index("time", inplace=True)
            frames[tf] = df

        # 2) Индикаторы на 3m
        df_3m = frames["3m"]
        df_3m["rsi_3m"] = ta.momentum.RSIIndicator(df_3m["close"], window=9).rsi()
        df_3m["ema_3m"] = ta.trend.EMAIndicator(df_3m["close"], window=21).ema_indicator()

        # Индикаторы на 5m
        df_5m = frames["5m"]
        df_5m["rsi_5m"] = ta.momentum.RSIIndicator(df_5m["close"], window=14).rsi()
        macd_5m = ta.trend.MACD(df_5m["close"])
        df_5m["macd_5m"] = macd_5m.macd()
        df_5m["macd_signal_5m"] = macd_5m.macd_signal()

        # Индикаторы на 15m
        df_15m = frames["15m"]
        df_15m["rsi_15m"] = ta.momentum.RSIIndicator(df_15m["close"], window=14).rsi()
        df_15m["atr_15m"] = ta.volatility.AverageTrueRange(df_15m["high"], df_15m["low"], df_15m["close"], window=14).average_true_range()
        df_15m["volume_ma_15m"] = df_15m["volume"].rolling(window=20).mean()
        df_15m["rel_volume_15m"] = df_15m["volume"] / df_15m["volume_ma_15m"]

        # 3) Поэтапный join
        df_final = df_3m.join(df_5m, how="inner", rsuffix="_5m")
        df_final = df_final.join(df_15m, how="inner", rsuffix="_15m")

        # Удаляем Nan
        df_final = df_final.dropna().reset_index()
        # Чтобы не было KeyError 'atr'
        df_final["atr"] = df_final["atr_15m"]

        fetch_debug[f"{symbol}_final_shape"] = df_final.shape
        log(f"[MultiTF] {symbol} ✅ df_final.shape = {df_final.shape}", level="DEBUG")

        # 4) (опционально) HTF-тренд
        if USE_HTF_CONFIRMATION:
            df_final["htf_trend"] = get_htf_trend(symbol)

        # 5) Придаём нужные поля, чтобы не было KeyError 'atr'
        df_final["ema"] = df_final["ema_3m"]
        df_final["rsi"] = df_final["rsi_5m"]
        df_final["macd"] = df_final["macd_5m"]
        df_final["macd_signal"] = df_final["macd_signal_5m"]
        df_final["rel_volume"] = df_final["rel_volume_15m"]
        df_final["volume_spike"] = df_final["rel_volume"] > 1.5

        # EMA crossover
        has_cross, _ = detect_ema_crossover(df_final)
        df_final["ema_cross"] = has_cross

        # Price Action
        df_final["candle_size"] = (df_final["close"] - df_final["open"]).abs()
        df_final["avg_candle_size"] = df_final["candle_size"].rolling(20).mean()
        df_final["price_action"] = df_final["candle_size"] > df_final["avg_candle_size"] * 1.5

        return df_final

    except Exception as e:
        log(f"[MultiTF] Error in fetch_data_multiframe for {symbol}: {e}", level="ERROR")
        return None

    finally:
        # Сохраняем debug-info в data/fetch_debug.json (длины raw, финальная shape)
        Path("data").mkdir(exist_ok=True)
        debug_path = Path("data/fetch_debug.json")
        try:
            with debug_path.open("w", encoding="utf-8") as f:
                json.dump(fetch_debug, f, indent=2)
        except Exception as e2:
            log(f"[MultiTF] Failed to write fetch_debug.json: {e2}", level="ERROR")


def get_enhanced_market_regime(symbol):
    """
    Расширенное определение рыночного режима: breakout, trend, flat, neutral
    """
    from common.config_loader import ADX_FLAT_THRESHOLD, ADX_TREND_THRESHOLD

    try:
        raw = fetch_ohlcv(symbol, timeframe="15m", limit=50)
        if not raw or len(raw) < 28:
            log(f"{symbol} ⚠️ Not enough candles for ADX", level="WARNING")
            return "neutral"

        highs = [r[2] for r in raw]
        lows = [r[3] for r in raw]
        closes = [r[4] for r in raw]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})

        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if adx_series.isna().all():
            return "neutral"
        adx = adx_series.iloc[-1]

        bb = ta.volatility.BollingerBands(df["close"], window=20)
        bb_width = (bb.bollinger_hband() - bb.bollinger_lband()).iloc[-1] / df["close"].iloc[-1]

        if BREAKOUT_DETECTION and bb_width > 0.05 and adx > 20:
            return "breakout"
        elif adx > ADX_TREND_THRESHOLD:
            return "trend"
        elif adx < ADX_FLAT_THRESHOLD:
            return "flat"
        else:
            return "neutral"
    except Exception as e:
        log(f"[Regime] error for {symbol}: {e}", level="ERROR")
        return "neutral"


# ---------------------------------------------------------------------------
# 2) passes_filters(...) и passes_unified_signal_check(...) — для фильтрации и структуры сигнала
# ---------------------------------------------------------------------------


def passes_filters(df: pd.DataFrame, symbol: str) -> bool:
    """
    Мультифреймовые фильтры: rsi_3m/5m/15m, ATR, rel_volume_15m...
    """
    try:
        config = get_runtime_config()
        rsi_threshold = config.get("rsi_threshold", 50)
        rel_vol_threshold = config.get("rel_volume_threshold", 0.5)
        relax = config.get("relax_factor", 0.5)
        use_multi = config.get("USE_MULTITF_LOGIC", False)

        # Учитываем relax_factor
        rel_vol_threshold = max(rel_vol_threshold * relax, 0.2)
        rsi_threshold = max(rsi_threshold * relax, 30)

        latest = df.iloc[-1]

        if use_multi:
            # Минимум 2 из 3 RSI >= порога
            rsi_hits = sum(1 for tf in ["rsi_3m", "rsi_5m", "rsi_15m"] if tf in latest and latest[tf] >= rsi_threshold)
            if rsi_hits < 2:
                log(f"{symbol} ⛔️ Filter fail: only {rsi_hits}/3 RSI above {rsi_threshold}", level="DEBUG")
                return False
            if latest.get("rel_volume_15m", 0) < rel_vol_threshold:
                log(f"{symbol} ⛔️ Filter fail: rel_volume_15m too low", level="DEBUG")
                return False
            if latest.get("atr_15m", 0) <= 0:
                log(f"{symbol} ⛔️ Filter fail: atr_15m missing or zero", level="DEBUG")
                return False
        else:
            # Fallback — проверяем только 15m
            if latest.get("rsi_15m", 0) < rsi_threshold:
                return False
            if latest.get("atr_15m", 0) <= 0:
                return False

        return True

    except Exception as e:
        log(f"[Filter] Error in passes_filters for {symbol}: {e}", level="ERROR")
        return False


def passes_unified_signal_check(score, breakdown):
    """
    Требование "1 основной + 1 дополнительный" индикатор.
    Основные: MACD, EMA_CROSS, RSI
    Дополнительные: Volume, HTF, PriceAction
    """
    has_primary = any(breakdown.get(ind, 0) > 0 for ind in ["MACD", "EMA_CROSS", "RSI"])
    has_secondary = any(breakdown.get(ind, 0) > 0 for ind in ["Volume", "HTF", "PriceAction"])

    # При слабом score (<2.5) требуется EMA_CROSS (или MACD_EMA, если бы было)
    if score < 2.5 and breakdown.get("EMA_CROSS", 0) <= 0:
        return False

    return has_primary and has_secondary


# ---------------------------------------------------------------------------
# 3) Основной метод should_enter_trade(...)
# ---------------------------------------------------------------------------


def should_enter_trade(symbol, exchange, last_trade_times, last_trade_times_lock):
    """
    Основная функция проверки входа в сделку:
    1) Грузим df через fetch_data_multiframe
    2) Фильтруем (passes_filters)
    3) Считаем score, проверяем min_score и unified_signal_check
    4) Рассчитываем risk_percent, TP/SL, notional, etc
    5) Возвращаем (direction, score, is_reentry) либо (None, [reasons])
    """

    from component_tracker import log_component_data
    from score_evaluator import calculate_score

    from common.config_loader import (
        DRY_RUN,
        LEVERAGE_MAP,
        MIN_NOTIONAL_OPEN,
        SHORT_TERM_MODE,
        SL_PERCENT,
        TAKER_FEE_RATE,
        USE_TESTNET,
        get_adaptive_min_score,
        get_min_net_profit,
    )
    from core.fail_stats_tracker import get_symbol_risk_factor
    from core.missed_signal_logger import log_missed_signal
    from core.position_manager import get_position_size
    from core.risk_utils import get_adaptive_risk_percent
    from core.tp_utils import calculate_tp_levels
    from core.trade_engine import calculate_order_quantity, trade_manager
    from open_interest_tracker import fetch_open_interest
    from stats import get_trade_stats
    from utils_core import get_cached_symbol_open_interest, log_score_history, send_telegram_message, update_cached_symbol_open_interest

    from . import get_enhanced_market_regime  # local import from this file

    failure_reasons = []

    # 1) fetch data
    df = fetch_data_multiframe(symbol)
    if df is None:
        log(f"Skipping {symbol} due to data fetch error (multiframe)", level="WARNING")
        failure_reasons.append("data_fetch_error")
        return None, failure_reasons

    # 2) trading hours (optional)
    from common.config_loader import get_priority_small_balance_pairs

    if TRADING_HOURS_FILTER and not is_optimal_trading_hour():
        balance = get_cached_balance()
        if balance < 300 and symbol in get_priority_small_balance_pairs():
            log(f"{symbol} Priority pair allowed in non-optimal hours", level="DEBUG")
        else:
            log(f"{symbol} ⏰ Non-optimal hours, skipping", level="DEBUG")
            failure_reasons.append("non_optimal_hours")
            return None, failure_reasons

    utc_now = datetime.utcnow()
    balance = get_cached_balance()
    position_size = get_position_size(symbol)

    # 3) margin check
    balance_info = exchange.fetch_balance()
    margin_info = balance_info["info"]
    total_margin_balance = float(margin_info.get("totalMarginBalance", 0))
    position_initial_margin = float(margin_info.get("totalPositionInitialMargin", 0))
    open_order_initial_margin = float(margin_info.get("totalOpenOrderInitialMargin", 0))
    available_margin = total_margin_balance - position_initial_margin - open_order_initial_margin
    if available_margin <= 0:
        log(f"⚠️ No available margin for {symbol}", level="ERROR")
        failure_reasons.append("insufficient_margin")
        return None, failure_reasons

    # 4) cooldown
    with last_trade_times_lock:
        last_time = last_trade_times.get(symbol)
        cooldown_sec = 20 * 60 if SHORT_TERM_MODE else 30 * 60
        elapsed = utc_now.timestamp() - (last_time.timestamp() if last_time else 0)
        if elapsed < cooldown_sec:
            if DRY_RUN:
                log(f"{symbol} ⏳ DRY_RUN cooldown skip")
            failure_reasons.append("cooldown_active")
            return None, failure_reasons

    # step2: filters
    if not passes_filters(df, symbol):
        failure_reasons.append("filter_reject")
        return None, failure_reasons

    # risk factor
    risk_factor, _ = get_symbol_risk_factor(symbol)
    if risk_factor < 0.25:
        log(f"{symbol} ⚠️ High risk factor={risk_factor:.2f}", level="WARNING")
    elif risk_factor < 1.0:
        log(f"{symbol} Risk factor={risk_factor:.2f}", level="DEBUG")

    # score check
    trade_count, winrate = get_trade_stats()
    score, breakdown = calculate_score(df, symbol, trade_count, winrate)

    # HTF confidence
    config = get_runtime_config()
    htf_conf = config.get("HTF_CONFIDENCE", 0.5)
    raw_score = score
    score *= 1 + (htf_conf - 0.5) * 0.4
    score = round(score, 2)

    log(f"{symbol} ⚙️ HTF confidence: {htf_conf:.2f} → score: {raw_score:.2f} → {score:.2f}", level="DEBUG")

    # OI boost
    prev_oi = get_cached_symbol_open_interest(symbol)
    curr_oi = fetch_open_interest(symbol)
    if prev_oi > 0 and curr_oi > prev_oi * 1.2:
        score += 0.2
        log(f"{symbol} OI +20% => +0.2 score", level="INFO")
    update_cached_symbol_open_interest(symbol, curr_oi)

    # min_required
    market_volatility = "medium"
    min_required = get_adaptive_min_score(balance, market_volatility, symbol)
    if SHORT_TERM_MODE and is_optimal_trading_hour():
        min_required *= 0.9

    if DRY_RUN:
        min_required *= 0.3
        log(f"{symbol} DRY_RUN final Score={score:.2f}, threshold={min_required:.2f}")

    if score < min_required:
        log(f"{symbol} ⏹ score {score:.2f}<{min_required:.2f}", level="DEBUG")
        failure_reasons.append("insufficient_score")
        log_missed_signal(symbol, score, breakdown, reason="insufficient_score")
        return None, failure_reasons

    # unified check
    if not passes_unified_signal_check(score, breakdown):
        log(f"{symbol} ❌ no 1+1 signals", level="INFO")
        log_missed_signal(symbol, score, breakdown, reason="signal_combo_fail")
        failure_reasons.append("signal_combo_fail")
        return None, failure_reasons

    # log breakdown

    log_component_data(symbol, breakdown)

    # direction from macd
    if "macd" not in df.columns or "macd_signal" not in df.columns:
        failure_reasons.append("missing_indicators")
        return None, failure_reasons

    macd_val = df["macd"].iloc[-1]
    macd_sig = df["macd_signal"].iloc[-1]
    direction = "BUY" if macd_val > macd_sig else "SELL"

    # risk
    entry_price = df["close"].iloc[-1]
    stop_price = entry_price * (1 - SL_PERCENT) if direction == "BUY" else entry_price * (1 + SL_PERCENT)
    base_risk = get_adaptive_risk_percent(balance)
    rmult = config.get("risk_multiplier", 1.0)
    base_risk *= rmult

    # extra confidence from breakdown
    dir_conf = 1.0
    if breakdown.get("EMA_CROSS", 0) > 0:
        dir_conf += 0.2
    if breakdown.get("Volume", 0) > 0:
        dir_conf += 0.2
    final_risk = min(base_risk * dir_conf, base_risk * 1.4)

    try:
        qty = calculate_order_quantity(entry_price, stop_price, balance, final_risk)
        if not qty:
            qty = MIN_NOTIONAL_OPEN / entry_price
    except Exception as e:
        log(f"{symbol} error qty calc: {e}", level="ERROR")
        failure_reasons.append("quantity_calculation_error")
        return None, failure_reasons

    # leverage
    if USE_TESTNET:
        lev_key = symbol.split(":")[0].replace("/", "")
    else:
        lev_key = symbol.replace("/", "")
    leverage = LEVERAGE_MAP.get(lev_key, 5)

    max_notional = balance * leverage
    notional = qty * entry_price
    if notional > max_notional:
        qty = max_notional / entry_price
        notional = qty * entry_price

    # TP/SL

    regime = get_enhanced_market_regime(symbol) if config.get("AUTO_TP_SL_ENABLED", True) else None

    tp1, tp2, sl_p, share1, share2 = calculate_tp_levels(entry_price, direction, regime, score, df)
    if tp1 is None or sl_p is None:
        failure_reasons.append("invalid_tp_sl")
        return None, failure_reasons

    # min net profit check

    gross_tp1 = (qty * share1) * abs(tp1 - entry_price)
    comm = 2 * (qty * entry_price * TAKER_FEE_RATE)
    net_tp1 = gross_tp1 - comm
    min_pnl = get_min_net_profit(balance)
    if net_tp1 < min_pnl:
        failure_reasons.append("insufficient_profit")
        return None, failure_reasons

    # re-entry logic
    with last_trade_times_lock:
        last_t = last_trade_times.get(symbol)
        now_ts = utc_now.timestamp()
        cd_elapsed = now_ts - (last_t.timestamp() if last_t else 0)
        last_closed = trade_manager.get_last_closed_time(symbol) or 0
        closed_elapsed = now_ts - last_closed
        last_scr = trade_manager.get_last_score(symbol) or 0

        if (cd_elapsed < cooldown_sec or closed_elapsed < cooldown_sec) and position_size == 0:
            if score <= 4:
                failure_reasons.append("cooldown_score_too_low")
                return None, failure_reasons
            direction = "BUY" if macd_val > macd_sig else "SELL"
            last_trade_times[symbol] = utc_now
            from telegram.telegram_utils import log_score_history

            if not DRY_RUN:
                log_score_history(symbol, score)
                log(f"{symbol} ✅ Re-entry {direction} (score={score:.2f}/5)")
            else:
                msg = f"🧪-DRY-REENTRY {symbol} {direction} s={score:.2f}/5"
                send_telegram_message(msg, force=True)
            return (("buy" if direction == "BUY" else "sell"), score, False, {}), []

        if last_scr and score - last_scr >= 1.5 and position_size == 0:
            direction = "BUY" if macd_val > macd_sig else "SELL"
            last_trade_times[symbol] = utc_now
            if not DRY_RUN:
                log_score_history(symbol, score)
                log(f"{symbol} ✅ Re-entry triggered (score={score:.2f}/5)")
            else:
                msg = f"🧪-DRY REENTRY2 {symbol} {direction} s={score:.2f}"
                send_telegram_message(msg, force=True)
            return (("buy" if direction == "BUY" else "sell"), score, True), []

    with last_trade_times_lock:
        last_trade_times[symbol] = utc_now

    # финальный возврат
    if not DRY_RUN:
        from telegram.telegram_utils import log_score_history

        log_score_history(symbol, score)
        log(f"{symbol} ✅ {direction} (score={score:.2f}/5)")
    else:
        msg = f"🧪-DRY {symbol} {direction} s={score:.2f}/5"
        send_telegram_message(msg, force=True)

    return (("buy" if direction == "BUY" else "sell"), score, False), []


# ---------------------------------------------------------------------------
# 4) Пример функции для вычисления TP целей (не обязательно)
# ---------------------------------------------------------------------------


def calculate_tp_targets():
    """
    Пример функции расчёта TP для уже открытых позиций
    """
    try:
        pos = trade_manager._trades  # Или exchange.fetch_positions()
        tp_targets = []
        for symbol, data in pos.items():
            entry_price = data.get("entry", 0)
            if entry_price > 0:
                tp_price = entry_price * 1.05
                tp_targets.append({"symbol": symbol, "entry_price": entry_price, "tp_price": tp_price})
                log(f"{symbol} => TP ~ {tp_price}", level="DEBUG")

        return tp_targets
    except Exception as e:
        log(f"Error calc TP: {e}", level="ERROR")
        return []
