import queue
import threading
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
from core.trade_engine import get_position_size
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
from utils_logging import log


def fetch_data(symbol, tf="15m"):
    def fetch_ohlcv_with_timeout():
        try:
            log(f"Starting fetch_ohlcv for {symbol} in thread", level="DEBUG")
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=50)
            log(f"Completed fetch_ohlcv for {symbol}", level="DEBUG")
            q.put(data)
        except Exception as e:
            log(f"Exception in fetch_ohlcv for {symbol}: {e}", level="ERROR")
            q.put(e)

    try:
        q = queue.Queue()
        fetch_thread = threading.Thread(target=fetch_ohlcv_with_timeout)
        fetch_thread.daemon = True
        fetch_thread.start()

        # Use threading.Timer to enforce timeout
        timeout = 10  # 10 seconds timeout
        timer = threading.Timer(timeout, lambda: q.put(TimeoutError("Fetch OHLCV timed out")))
        timer.start()

        # Wait for the thread to complete or timeout
        fetch_thread.join(timeout=timeout)
        timer.cancel()  # Cancel the timer if the thread completes

        if fetch_thread.is_alive():
            log(f"Force stopping fetch thread for {symbol} after timeout", level="ERROR")
            fetch_thread._stop()  # Attempt to stop the thread (not guaranteed to work)
            return None

        result = q.get()
        if isinstance(result, Exception):
            log(f"Error fetching OHLCV data for {symbol}: {result}", level="ERROR")
            return None

        data = result
        if not data:
            log(f"No data returned for {symbol} on timeframe {tf}", level="ERROR")
            raise ValueError("No data returned from exchange")
        df = pd.DataFrame(
            data,
            columns=["time", "open", "high", "low", "close", "volume"],
        )
        if df.empty or len(df) < 14:
            log(
                f"Insufficient data for {symbol} on timeframe {tf} (rows: {len(df)})", level="ERROR"
            )
            raise ValueError("Insufficient data for indicator calculation")

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
        log(f"Error fetching or processing data for {symbol}: {e}", level="ERROR")
        return None


def get_htf_trend(symbol, tf="1h"):
    df_htf = fetch_data(symbol, tf=tf)
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
            pass
        else:
            last_time = None

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

    buy_score = 0
    sell_score = 0

    if rsi < 35:
        buy_score += 1
    if rsi > 65:
        sell_score += 1

    if macd > macd_signal - abs(macd_signal) * 0.1:
        buy_score += 1
    if macd < macd_signal + abs(macd_signal) * 0.1:
        sell_score += 1

    if price > ema * 0.99:
        buy_score += 1
    if price < ema * 1.01:
        sell_score += 1

    if htf_trend:
        buy_score += 1
    if not htf_trend:
        sell_score += 1

    if has_long_position:
        sell_score += 1
        buy_score -= 1
    if has_short_position:
        buy_score += 1
        sell_score -= 1

    if available_margin < 10:
        if has_long_position:
            sell_score += 1
        if has_short_position:
            buy_score += 1
        if not has_long_position and not has_short_position:
            buy_score -= 1
            sell_score -= 1

    if DRY_RUN:
        log(f"{symbol} 🔎 Buy Score: {buy_score}/5, Sell Score: {sell_score}/5")

    with last_trade_times_lock:
        if last_time and (utc_now - last_time).total_seconds() < 1800:
            if buy_score < 4 and sell_score < 4:
                if DRY_RUN:
                    log(
                        f"{symbol} ⏳ Ignored due to cooldown (scores: {buy_score}/5, {sell_score}/5)"
                    )
                return None
            else:
                log(
                    f"{symbol} ⚠️ Cooldown skipped due to strong signal (scores: {buy_score}/5, {sell_score}/5)"
                )

        if buy_score < MIN_TRADE_SCORE and sell_score < MIN_TRADE_SCORE:
            if DRY_RUN:
                log(f"{symbol} ❌ No entry: insufficient score")
            return None

        last_trade_times[symbol] = utc_now

    if buy_score >= sell_score and buy_score >= MIN_TRADE_SCORE:
        if DRY_RUN:
            log(f"{symbol} 🧪 [DRY_RUN] Signal → BUY, score: {buy_score}/5")
            send_telegram_message(
                escape_markdown_v2(f"🧪 [DRY_RUN] {symbol} → BUY | Score: {buy_score}/5"),
                force=True,
            )
        log(f"{symbol} ✅ BUY signal triggered (score: {buy_score}/5)")
        return "buy", buy_score
    elif sell_score >= MIN_TRADE_SCORE:
        if DRY_RUN:
            log(f"{symbol} 🧪 [DRY_RUN] Signal → SELL, score: {sell_score}/5")
            send_telegram_message(
                escape_markdown_v2(f"🧪 [DRY_RUN] {symbol} → SELL | Score: {sell_score}/5"),
                force=True,
            )
        log(f"{symbol} ✅ SELL signal triggered (score: {sell_score}/5)")
        return "sell", sell_score

    return None
