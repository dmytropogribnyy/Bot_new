import threading  # Fix: Add threading import
from datetime import datetime

import pandas as pd
import ta

from config import (
    DRY_RUN,
    FILTER_THRESHOLDS,
    MIN_TRADE_SCORE,
    VOLATILITY_ATR_THRESHOLD,
    VOLATILITY_RANGE_THRESHOLD,
    VOLATILITY_SKIP_ENABLED,
    exchange,
)
from core.trade_engine import get_position_size  # Keep for should_enter_trade
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance  # Keep for should_enter_trade
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
        return False  # Default to False if data fetch fails
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
    rsi = df["rsi"].iloc[-1]
    ema = df["ema"].iloc[-1]
    macd = df["macd"].iloc[-1]
    macd_signal = df["macd_signal"].iloc[-1]
    htf_trend = get_htf_trend(symbol)

    if DRY_RUN:
        log(
            f"{symbol} 🔎 RSI: {rsi:.1f}, MACD: {macd:.5f}, Signal: {macd_signal:.5f}, EMA: {ema:.5f}, HTF: {htf_trend}"
        )

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

    score = 0
    if rsi < 30 or rsi > 70:
        score += 1
    if (macd > macd_signal and rsi < 50) or (macd < macd_signal and rsi > 50):
        score += 1
    if (macd > macd_signal and price > ema) or (macd < macd_signal and price < ema):
        score += 1
    if htf_trend and price > ema:
        score += 1

    if has_long_position:
        score -= 1  # Avoid opening another long position
    if has_short_position:
        score -= 1  # Avoid opening another short position

    if available_margin < 10:
        score -= 1  # Avoid new positions if margin is low

    if DRY_RUN:
        log(f"{symbol} 🔎 Final Score: {score}/5")

    if score < MIN_TRADE_SCORE:
        if DRY_RUN:
            log(f"{symbol} ❌ No entry: insufficient score")
        return None

    with last_trade_times_lock:
        last_trade_times[symbol] = utc_now

    if DRY_RUN:
        log(
            f"{symbol} 🧪 [DRY_RUN] Signal → {('BUY' if macd > macd_signal else 'SELL')}, score: {score}/5"
        )
        send_telegram_message(
            escape_markdown_v2(
                f"🧪 [DRY_RUN] {symbol} → {('BUY' if macd > macd_signal else 'SELL')} | Score: {score}/5"
            ),
            force=True,
        )
    log(
        f"{symbol} ✅ {('BUY' if macd > macd_signal else 'SELL')} signal triggered (score: {score}/5)"
    )
    return ("buy" if macd > macd_signal else "sell", score)
