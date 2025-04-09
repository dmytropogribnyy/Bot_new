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
from core.trade_engine import get_position_size
from telegram.telegram_utils import send_telegram_message
from tp_logger import get_trade_stats
from utils_core import get_cached_balance
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def fetch_data(symbol, tf="15m"):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=50)
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


def should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock):
    if df is None:
        log(f"Skipping {symbol} due to data fetch error", level="WARNING")
        return None

    utc_now = datetime.utcnow()
    with last_trade_times_lock:
        last_time = last_trade_times.get(symbol)
        if last_time and (utc_now - last_time).total_seconds() < 1800:
            if DRY_RUN:
                log(f"{symbol} ⏳ Ignored due to cooldown")
            return None

    balance = get_cached_balance()
    position_size = get_position_size(symbol)
    has_long_position = position_size > 0
    has_short_position = position_size < 0
    available_margin = balance * 0.1

    filters = FILTER_THRESHOLDS.get(symbol, {})
    atr_thres = filters.get("atr", 0.0015)
    adx_thres = filters.get("adx", 7)
    bb_thres = filters.get("bb", 0.008)

    if DRY_RUN:
        atr_thres *= 0.6
        adx_thres *= 0.6
        bb_thres *= 0.6

    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1]
    adx_val = df["adx"].iloc[-1]
    bb_width = df["bb_width"].iloc[-1]
    get_htf_trend(symbol)

    if VOLATILITY_SKIP_ENABLED:
        high = df["high"].iloc[-1]
        low = df["low"].iloc[-1]
        range_ratio = (high - low) / price
        if atr / price < VOLATILITY_ATR_THRESHOLD and range_ratio < VOLATILITY_RANGE_THRESHOLD:
            if DRY_RUN:
                log(
                    f"{symbol} ⛔️ Rejected: low volatility (ATR: {atr / price:.5f}, Range: {range_ratio:.5f})"
                )
            return None

    if atr / price < atr_thres:
        if DRY_RUN:
            log(f"{symbol} ⛔️ Rejected: ATR too low ({atr / price:.5f} < {atr_thres})")
        return None
    if adx_val < adx_thres:
        if DRY_RUN:
            log(f"{symbol} ⛔️ Rejected: ADX too low ({adx_val:.2f} < {adx_thres})")
        return None
    if bb_width / price < bb_thres:
        if DRY_RUN:
            log(f"{symbol} ⛔️ Rejected: BB Width too low ({bb_width / price:.5f} < {bb_thres})")
        return None

    score = calculate_score(df, symbol)

    trade_count, winrate = get_trade_stats()
    min_required = get_adaptive_min_score(trade_count, winrate)

    # Снижаем порог в DRY_RUN для более частых сигналов
    if DRY_RUN:
        min_required *= 0.3  # Снижаем с 3.5 до 1.05

    if DRY_RUN:
        log(f"{symbol} 🔎 Final Score: {score}/5 (Required: {min_required})")

    if has_long_position or has_short_position or available_margin < 10:
        score -= 0.5

    if score < min_required:
        if DRY_RUN:
            log(f"{symbol} ❌ No entry: insufficient score")
        return None

    with last_trade_times_lock:
        last_trade_times[symbol] = utc_now

    direction = "BUY" if df["macd"].iloc[-1] > df["macd_signal"].iloc[-1] else "SELL"

    if DRY_RUN:
        log(f"{symbol} 🧪 [DRY_RUN] Signal → {direction}, score: {score}/5")
        msg = f"🧪-DRY-RUN-{symbol}-{direction}-Score-{round(score, 2)}-of-5"
        send_telegram_message(msg, force=True, parse_mode="")
    else:
        log(f"{symbol} ✅ {direction} signal triggered (score: {score}/5)")

    return ("buy" if direction == "BUY" else "sell", score)
