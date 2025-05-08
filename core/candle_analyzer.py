# core/candle_analyzer.py
"""
Optimized candle pattern analysis module for BinanceBot
Provides fast and effective entry confirmation for real-time trading
Balanced between speed and accuracy with minimal reversal pattern checks
Optimized for 15-minute timeframe trading
"""

import hashlib
import time

import numpy as np

from utils_logging import log

# Кэш для результатов check_trend_continuation
trend_cache = {}
TREND_CACHE_TIMEOUT = 60  # Время жизни кэша в секундах


def clean_trend_cache():
    """
    Clean the trend cache by removing stale entries.
    """
    current_time = time.time()
    keys_to_remove = [key for key, (_, timestamp) in trend_cache.items() if current_time - timestamp > TREND_CACHE_TIMEOUT]
    for key in keys_to_remove:
        trend_cache.pop(key, None)
    log(f"Cleaned trend cache, removed {len(keys_to_remove)} stale entries", level="DEBUG")


def check_candle_strength(df, lookback=3, direction="buy"):
    """
    Checks candle strength for entry confirmation

    Args:
        df (pandas.DataFrame): DataFrame with OHLCV data
        lookback (int): Number of recent candles to analyze
        direction (str): Trade direction ('buy' or 'sell')

    Returns:
        bool: True if candles confirm entry, False otherwise
    """
    if len(df) < lookback:
        log(f"Insufficient data for candle analysis: {len(df)} candles, need at least {lookback}", level="WARNING")
        return True  # Default allow if insufficient data

    recent_candles = df.iloc[-lookback:]

    # For buy signals (long entries)
    if direction.lower() == "buy":
        # Calculate bodies of candles (close - open for bullish candles)
        bodies = recent_candles["close"] - recent_candles["open"]
        bull_bodies = bodies[bodies > 0]

        if len(bull_bodies) == 0:
            log(f"Entry rejected: No bullish candles in last {lookback} periods", level="INFO")
            return False  # No bullish candles in recent lookback

        # Calculate average body size of bullish candles
        avg_body = bull_bodies.mean()
        # Get the body size of the most recent candle
        last_body = bodies.iloc[-1]

        # Calculate body to range ratio for the last candle
        last_candle = recent_candles.iloc[-1]
        last_range = last_candle["high"] - last_candle["low"]
        body_range_ratio = abs(last_body) / last_range if last_range > 0 else 0

        # If last candle is weak or bearish, reject signal
        if last_body <= 0:
            log("Entry rejected: Last candle is bearish for buy signal", level="INFO")
            return False
        if last_body < avg_body * 0.6:
            log(f"Entry rejected: Last candle too weak ({last_body:.6f} vs avg {avg_body:.6f})", level="INFO")
            return False
        if body_range_ratio < 0.5:
            log(f"Entry rejected: Last candle has large wicks (body/range ratio: {body_range_ratio:.2f})", level="INFO")
            return False

        # Check if volume is decreasing (weakness)
        volumes = recent_candles["volume"].values
        if volumes[-1] < volumes[-2] * 0.7:
            log("Entry warning: Decreasing volume on latest candle", level="DEBUG")
            # Don't reject solely based on volume, just log a warning

    # For sell signals (short entries)
    elif direction.lower() == "sell":
        # Calculate bodies of candles (open - close for bearish candles)
        bodies = recent_candles["open"] - recent_candles["close"]
        bear_bodies = bodies[bodies > 0]

        if len(bear_bodies) == 0:
            log(f"Entry rejected: No bearish candles in last {lookback} periods", level="INFO")
            return False  # No bearish candles in recent lookback

        # Calculate average body size of bearish candles
        avg_body = bear_bodies.mean()
        # Get the body size of the most recent candle
        last_body = bodies.iloc[-1]

        # Calculate body to range ratio for the last candle
        last_candle = recent_candles.iloc[-1]
        last_range = last_candle["high"] - last_candle["low"]
        body_range_ratio = abs(last_body) / last_range if last_range > 0 else 0

        # If last candle is weak or bullish, reject signal
        if last_body <= 0:
            log("Entry rejected: Last candle is bullish for sell signal", level="INFO")
            return False
        if last_body < avg_body * 0.6:
            log(f"Entry rejected: Last candle too weak ({last_body:.6f} vs avg {avg_body:.6f})", level="INFO")
            return False
        if body_range_ratio < 0.5:
            log(f"Entry rejected: Last candle has large wicks (body/range ratio: {body_range_ratio:.2f})", level="INFO")
            return False

        # Check if volume is decreasing (weakness)
        volumes = recent_candles["volume"].values
        if volumes[-1] < volumes[-2] * 0.7:
            log("Entry warning: Decreasing volume on latest candle", level="DEBUG")
            # Don't reject solely based on volume, just log a warning

    return True


def check_trend_continuation(df, direction="buy", window=10):
    """
    Check if recent candles indicate trend continuation

    Args:
        df (pandas.DataFrame): DataFrame with OHLCV data
        direction (str): Trade direction ('buy' or 'sell')
        window (int): Number of candles to consider for trend

    Returns:
        float: Trend strength score (0-1), higher is stronger
    """
    if len(df) < window:
        return 0.5  # Neutral if insufficient data

    # Создаём ключ для кэша на основе данных (хэшируем параметры)
    cache_key = hashlib.md5(f"{df.index[-1]}{direction}{window}".encode()).hexdigest()
    current_time = time.time()

    # Проверяем, есть ли результат в кэше и не устарел ли он
    if cache_key in trend_cache:
        cached_result, timestamp = trend_cache[cache_key]
        if current_time - timestamp < TREND_CACHE_TIMEOUT:
            log(f"Using cached trend continuation result for key {cache_key}", level="DEBUG")
            return cached_result

    recent_df = df.iloc[-window:]

    # Calculate simple trend metrics
    close_prices = recent_df["close"].values

    # Percentage of up-candles vs down-candles
    up_candles = sum(recent_df["close"] > recent_df["open"])
    down_candles = sum(recent_df["close"] < recent_df["open"])
    up_ratio = up_candles / (up_candles + down_candles) if (up_candles + down_candles) > 0 else 0.5

    # Linear regression slope of closing prices
    x = np.arange(len(close_prices))
    slope, _ = np.polyfit(x, close_prices, 1)
    normalized_slope = min(max(slope / (close_prices.mean() * 0.01), -1), 1)  # Scale to [-1, 1]

    # Calculate momentum
    momentum = (close_prices[-1] / close_prices[0]) - 1

    # Combine metrics based on direction
    if direction.lower() == "buy":
        trend_score = (
            (up_ratio * 0.4)  # Weight of up/down ratio
            + (max(normalized_slope, 0) * 0.4)  # Weight of slope (only positive matters)
            + (max(momentum, 0) * 0.2)  # Weight of momentum (only positive matters)
        )
    else:  # sell
        trend_score = (
            ((1 - up_ratio) * 0.4)  # Weight of down/up ratio
            + (max(-normalized_slope, 0) * 0.4)  # Weight of negative slope
            + (max(-momentum, 0) * 0.2)  # Weight of negative momentum
        )

    # Ensure result is in [0, 1]
    trend_score = min(max(trend_score, 0), 1)

    # Сохраняем результат в кэш
    trend_cache[cache_key] = (trend_score, current_time)
    log(f"Cached trend continuation result for key {cache_key}", level="DEBUG")
    # Очищаем кэш после добавления новой записи
    clean_trend_cache()

    return trend_score


def evaluate_entry_quality(df, direction="buy"):
    """
    Optimized evaluation of entry quality based on candle patterns
    Includes minimal reversal pattern checks for efficiency

    Args:
        df (pandas.DataFrame): DataFrame with OHLCV data
        direction (str): Trade direction ('buy' or 'sell')

    Returns:
        tuple: (bool, float) - (Entry valid, Quality score 0-1)
    """
    # Check for basic candle strength
    if not check_candle_strength(df, lookback=3, direction=direction):
        return False, 0.0

    # Minimal reversal pattern checks (Doji and Engulfing)
    if len(df) >= 2:
        recent_df = df.iloc[-2:]
        last_candle = recent_df.iloc[-1]
        candle_range = last_candle["high"] - last_candle["low"]
        if candle_range > 0:
            body = abs(last_candle["close"] - last_candle["open"])
            if body / candle_range < 0.1:
                log("Reversal pattern detected: Doji (indecision)", level="WARNING")
                return False, 0.0
        if direction.lower() == "buy":
            if (
                recent_df["open"].iloc[-1] > recent_df["close"].iloc[-2]
                and recent_df["close"].iloc[-1] < recent_df["open"].iloc[-2]
                and recent_df["close"].iloc[-2] > recent_df["open"].iloc[-2]
            ):
                log("Reversal pattern detected: Bearish engulfing", level="WARNING")
                return False, 0.0
        elif direction.lower() == "sell":
            if (
                recent_df["open"].iloc[-1] < recent_df["close"].iloc[-2]
                and recent_df["close"].iloc[-1] > recent_df["open"].iloc[-2]
                and recent_df["close"].iloc[-2] < recent_df["open"].iloc[-2]
            ):
                log("Reversal pattern detected: Bullish engulfing", level="WARNING")
                return False, 0.0

    # Calculate trend continuation strength
    trend_score = check_trend_continuation(df, direction=direction)
    quality_score = trend_score

    # Higher threshold for small accounts
    from utils_core import get_cached_balance

    balance = get_cached_balance()
    min_quality = 0.4 if balance < 150 else 0.3

    # Log quality assessment (только если не проходит порог)
    if quality_score < min_quality:
        log(f"Entry quality score for {direction}: {quality_score:.2f} (minimum: {min_quality:.2f})", level="INFO")

    # Return validity and quality score
    return quality_score >= min_quality, quality_score
