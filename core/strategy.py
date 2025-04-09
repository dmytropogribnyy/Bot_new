# strategy.py
import threading
from datetime import datetime

import pandas as pd
import ta

from config import (
    DRY_RUN,
    FILTER_THRESHOLDS,
    VOLATILITY_ATR_THRESHOLD,
    VOLATILITY_RANGE_THRESHOLD,
    VOLATILITY_SKIP_ENABLED,
    exchange,
)
from core.score_evaluator import calculate_score, get_adaptive_min_score
from core.trade_engine import get_position_size, trade_manager
from core.volatility_controller import get_volatility_filters
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_cached_balance, safe_call_retry
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def fetch_data(symbol, tf="15m"):
    try:
        data = safe_call_retry(
            exchange.fetch_ohlcv, symbol, timeframe=tf, limit=50, label=f"fetch_ohlcv {symbol}"
        )
        if not data:
            log(f"No data returned for {symbol} on timeframe {tf}", level="ERROR")
            return None
        df = pd.DataFrame(
            data,
            columns=["time", "open", "high", "low", "close", "volume"],
        )
        if df.empty:
            log(f"Empty DataFrame for {symbol} on timeframe {tf}", level="ERROR")
            return None
        if len(df) < 14:
            log(f"Not enough data for {symbol} on timeframe {tf} (rows: {len(df)})", level="ERROR")
            return None
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        df["ema"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
        df["macd"] = ta.trend.MACD(df["close"]).macd()
        df["macd_signal"] = ta.trend.MACD(df["close"]).macd_signal()
        df["atr"] = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()
        df["fast_ema"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
        df["slow_ema"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
        df["adx"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        bb = ta.volatility.BollingerBands(df["close"], window=20)
        df["bb_width"] = bb.bollinger_hband() - bb.bollinger_lband()
        return df
    except Exception as e:
        log(f"Error fetching data for {symbol}: {e}", level="ERROR")
        return None


def get_htf_trend(symbol, tf="1h"):
    df_htf = fetch_data(symbol, tf=tf)
    if df_htf is None:
        return False
    return df_htf["close"].iloc[-1] > df_htf["ema"].iloc[-1]


def passes_filters(df, symbol):
    balance = get_cached_balance()
    filter_mode = "default_light" if balance < 100 else "default"
    base_filters = FILTER_THRESHOLDS.get(symbol, FILTER_THRESHOLDS[filter_mode])

    filters = get_volatility_filters(symbol, base_filters)
    relax_factor = filters["relax_factor"]

    if DRY_RUN:
        filters["atr"] *= 0.6
        filters["adx"] *= 0.6
        filters["bb"] *= 0.6

    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1] / price
    adx = df["adx"].iloc[-1]
    bb_width = df["bb_width"].iloc[-1] / price

    if atr < filters["atr"]:
        log(
            f"{symbol} ⛔️ Rejected: ATR {atr:.5f} < {filters['atr']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    if adx < filters["adx"]:
        log(
            f"{symbol} ⛔️ Rejected: ADX {adx:.2f} < {filters['adx']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    if bb_width < filters["bb"]:
        log(
            f"{symbol} ⛔️ Rejected: BB Width {bb_width:.5f} < {filters['bb']} (relax={relax_factor})",
            level="DEBUG",
        )
        return False
    return True


# strategy.py (фрагмент)
def should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock):
    if df is None:
        log(f"Skipping {symbol} due to data fetch error", level="WARNING")
        return None

    utc_now = datetime.utcnow()
    balance = get_cached_balance()
    position_size = get_position_size(symbol)
    has_long_position = position_size > 0
    has_short_position = position_size < 0
    available_margin = balance * 0.1

    with last_trade_times_lock:
        last_time = last_trade_times.get(symbol)
        cooldown = 30 * 60  # 30 минут в секундах
        elapsed = utc_now.timestamp() - last_time.timestamp() if last_time else float("inf")

        if elapsed < 1800:  # Базовый cooldown
            if DRY_RUN:
                log(f"{symbol} ⏳ Ignored due to cooldown")
            return None

    if VOLATILITY_SKIP_ENABLED:
        price = df["close"].iloc[-1]
        high = df["high"].iloc[-1]
        low = df["low"].iloc[-1]
        atr = df["atr"].iloc[-1] / price
        range_ratio = (high - low) / price
        if atr < VOLATILITY_ATR_THRESHOLD and range_ratio < VOLATILITY_RANGE_THRESHOLD:
            if DRY_RUN:
                log(
                    f"{symbol} ⛔️ Rejected: low volatility (ATR: {atr:.5f}, Range: {range_ratio:.5f})"
                )
            return None

    if not passes_filters(df, symbol):
        return None

    trade_count, winrate = get_trade_stats()
    score = calculate_score(df, symbol, trade_count, winrate)
    min_required = get_adaptive_min_score(trade_count, winrate)

    if DRY_RUN:
        min_required *= 0.3

    if DRY_RUN:
        log(f"{symbol} 🔎 Final Score: {score}/5 (Required: {min_required})")

    if has_long_position or has_short_position or available_margin < 10:
        score -= 0.5

    # Smart Re-entry Logic
    with last_trade_times_lock:
        last_time = last_trade_times.get(symbol)
        now = utc_now.timestamp()
        elapsed = now - last_time.timestamp() if last_time else float("inf")

        last_closed_time = trade_manager.get_last_closed_time(symbol)
        closed_elapsed = now - last_closed_time if last_closed_time else float("inf")
        last_score = trade_manager.get_last_score(symbol)

        # Re-entry после ручного закрытия или в течение cooldown
        if (elapsed < cooldown or closed_elapsed < cooldown) and position_size == 0:
            if score <= 4:
                log(f"Skipping {symbol}: cooldown active, score {score} <= 4", level="DEBUG")
                return None
            log(f"Re-entry signal for {symbol}: score {score} > 4 within cooldown", level="INFO")
            direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
                level="DEBUG",
            )
            last_trade_times[symbol] = utc_now
            if DRY_RUN:
                log(f"{symbol} 🧪 [DRY_RUN] Re-entry Signal → {direction}, score: {score}/5")
                msg = f"🧪-DRY-RUN-REENTRY-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
                send_telegram_message(msg, force=True, parse_mode="")
            else:
                log(f"{symbol} ✅ Re-entry {direction} signal triggered (score: {score}/5)")
            return ("buy" if direction == "BUY" else "sell", score, True)

        # Re-entry при улучшении score
        if last_score and score - last_score >= 1.5 and position_size == 0:
            log(f"Re-entry allowed for {symbol}: score {score} vs last {last_score}", level="INFO")
            last_trade_times[symbol] = utc_now
            direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
            log(
                f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
                level="DEBUG",
            )
            if DRY_RUN:
                log(f"{symbol} 🧪 [DRY_RUN] Re-entry Signal → {direction}, score: {score}/5")
                msg = f"🧪-DRY-RUN-REENTRY-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
                send_telegram_message(msg, force=True, parse_mode="")
            else:
                log(f"{symbol} ✅ Re-entry {direction} signal triggered (score: {score}/5)")
            return ("buy" if direction == "BUY" else "sell", score, True)

    # Обычный вход
    if score < min_required:
        if DRY_RUN:
            log(f"{symbol} ❌ No entry: insufficient score")
        return None

    with last_trade_times_lock:
        last_trade_times[symbol] = utc_now

    direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"
    log(
        f"{symbol} 🔍 Generated signal: {direction}, MACD: {df['macd'].iloc[-1]:.5f}, Signal: {df['macd_signal'].iloc[-1]:.5f}",
        level="DEBUG",
    )
    if DRY_RUN:
        log(f"{symbol} 🧪 [DRY_RUN] Signal → {direction}, score: {score}/5")
        msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
        send_telegram_message(msg, force=True, parse_mode="")
    else:
        log(f"{symbol} ✅ {direction} signal triggered (score: {score}/5)")
    return ("buy" if direction == "BUY" else "sell", score, False)
