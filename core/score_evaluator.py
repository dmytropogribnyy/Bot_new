# score_evaluator.py
import threading
from datetime import datetime

import pytz

from common.config_loader import (
    DRY_RUN,
    get_priority_small_balance_pairs,
)
from utils_core import get_runtime_config
from utils_logging import log

last_score_data = {}
last_score_lock = threading.Lock()
# Track win/loss by signal type for adaptive learning
signal_performance = {
    "RSI": {"wins": 0, "losses": 0},
    "HTF": {"wins": 0, "losses": 0},
    "VOLUME": {"wins": 0, "losses": 0},
    "EMA_CROSS": {"wins": 0, "losses": 0},
    "VOL_SPIKE": {"wins": 0, "losses": 0},
    "PRICE_ACTION": {"wins": 0, "losses": 0},
}


def get_adaptive_min_score(balance, market_volatility=None, symbol=None):
    """
    Get adaptive minimum score required for trade entry based on conditions
    with relax_boost factor applied for dynamic adjustment
    """
    # Base threshold based on account size
    if balance < 120:
        base_threshold = 2.3  # Lower threshold for micro accounts
    elif balance < 300:  # Updated from 250 to 300
        base_threshold = 2.8  # Moderate threshold for small accounts
    else:
        base_threshold = 3.3  # Higher threshold for larger accounts

    # Adjust for market volatility
    vol_adjustment = 0
    if market_volatility == "high":
        vol_adjustment = -0.6  # More lenient during high volatility
    elif market_volatility == "low":
        vol_adjustment = +0.4  # More strict during low volatility

    # Adjustment for trading session (time of day)
    # Only consider deep night hours (3-7 UTC) as inactive
    inactive_hours = [3, 4, 5, 6, 7]
    hour_utc = datetime.now(pytz.UTC).hour
    session_adjustment = 0

    if hour_utc in inactive_hours:
        session_adjustment = +0.2  # More strict during deep night hours
    else:
        session_adjustment = -0.2  # More lenient during all other hours

    # Symbol-specific adjustment (priority pairs for small accounts)
    symbol_adjustment = 0
    if balance < 300 and symbol and symbol.split("/")[0] in ["XRP", "DOGE", "ADA", "MATIC", "DOT"]:
        symbol_adjustment = -0.2  # Bonus for small account priority pairs

    # Apply score_relax_boost from runtime_config for dynamic activity adjustment
    runtime_config = get_runtime_config()
    relax_boost = runtime_config.get("score_relax_boost", 1.0)

    # DRY_RUN mode uses lower threshold for testing
    dry_run_factor = 0.3 if DRY_RUN else 1.0

    # Calculate final threshold with all adjustments applied
    raw_threshold = (base_threshold + vol_adjustment + session_adjustment + symbol_adjustment) * dry_run_factor
    threshold = raw_threshold / relax_boost  # Apply relax boost as divisor

    log(f"{symbol} Adaptive min_score: {threshold:.2f} (base={base_threshold}, relax_boost={relax_boost})", level="DEBUG")

    return max(1.8, threshold)  # Minimum floor of 1.8


def get_risk_percent_by_score(balance, score, win_streak=0, symbol=None):
    """
    Adaptive risk percentage based on score, account size, and recent performance.
    Enhanced for short-term trading with win streak consideration.
    """
    from utils_core import get_adaptive_risk_percent

    # Get base risk based on account size
    base_risk = get_adaptive_risk_percent(balance)

    # Win streak bonus - reward consecutive wins
    streak_bonus = min(win_streak * 0.002, 0.008)  # Up to +0.8% for win streaks

    # Priority pair bonus for small accounts
    priority_bonus = 0.0
    if balance < 300 and symbol in get_priority_small_balance_pairs():
        priority_bonus = 0.002  # +0.2% for priority pairs

    # Score-based adjustment
    if score < 3.0:
        score_factor = 0.6  # 60% of base risk (up from 50%)
    elif score < 3.5:
        score_factor = 0.8  # 80% of base risk (up from 75%)
    elif score < 4.0:
        score_factor = 1.0  # 100% - unchanged
    elif score < 4.5:
        score_factor = 1.2  # 120% - unchanged
    else:
        score_factor = 1.3  # 130% for exceptional signals (new tier)

    # Calculate risk with all factors
    risk = (base_risk * score_factor) + streak_bonus + priority_bonus

    # Cap at reasonable limits
    if balance < 100:
        max_risk = 0.015  # Max 1.5% for ultra-small accounts
    elif balance < 300:
        max_risk = 0.025  # Max 2.5% for small accounts
    else:
        max_risk = 0.05  # Max 5% for larger accounts

    return min(risk, max_risk)


def get_required_risk_reward_ratio(score, symbol=None, balance=None):
    # Значительно снижаем базовые требования
    if score < 3.0:
        base_rr = 0.98  # Снижено с 1.8
    elif score < 3.5:
        base_rr = 0.8  # Снижено с 1.5
    elif score < 4.0:
        base_rr = 0.7  # Снижено с 1.3
    else:
        base_rr = 0.6  # Снижено с 1.2

    # Повышаем скидку для приоритетных пар
    if balance and balance < 300 and symbol in get_priority_small_balance_pairs():
        base_rr *= 0.6  # 40% скидка вместо 10%

    # Дополнительная скидка для очень малых депозитов
    if balance and balance < 100:
        base_rr *= 0.8  # Ещё 20% скидка для депозитов <100 USDC

    return base_rr


# В самом начале файла score_evaluator.py (после import'ов)
def detect_ema_crossover(df, fast_window=9, slow_window=21):
    """
    Определяет факт пересечения EMA (быстрой и медленной) на последней свече.
    Возвращает (has_crossover: bool, direction: int)
    direction = +1 (пересечение вверх), -1 (пересечение вниз), 0 (нет сигнала)
    """
    import ta

    fast_ema = ta.trend.EMAIndicator(df["close"], window=fast_window).ema_indicator()
    slow_ema = ta.trend.EMAIndicator(df["close"], window=slow_window).ema_indicator()

    prev_fast = fast_ema.iloc[-2]
    prev_slow = slow_ema.iloc[-2]
    curr_fast = fast_ema.iloc[-1]
    curr_slow = slow_ema.iloc[-1]

    if prev_fast < prev_slow and curr_fast > curr_slow:
        return True, 1  # пересечение вверх
    elif prev_fast > prev_slow and curr_fast < curr_slow:
        return True, -1  # пересечение вниз
    else:
        return False, 0  # нет сигнала


def detect_volume_spike(df, lookback=5, threshold=1.5):
    """
    New function: Detect recent volume spike for increased momentum.
    """
    if len(df) < lookback + 1:
        return False

    recent_volume = df["volume"].iloc[-1]
    avg_volume = df["volume"].iloc[-(lookback + 1) : -1].mean()

    if recent_volume > avg_volume * threshold:
        return True

    return False


def calculate_score(df, symbol=None, trade_count=0, winrate=0.0):
    """
    Считает итоговый score пары (от 0.0 до ~5.0)
    на основе MACD, RSI, EMA-cross, volume_spike, etc.
    """
    import math

    from utils_core import get_cached_balance, get_runtime_config
    from utils_logging import log

    _config = get_runtime_config()
    _balance = get_cached_balance()

    latest = df.iloc[-1]
    _price = latest["close"]
    rsi = latest.get("rsi", 0)
    macd = latest.get("macd", 0)
    macd_signal = latest.get("macd_signal", 0)
    htf_trend = latest.get("htf_trend", False)
    volume_spike = latest.get("volume_spike", False)
    price_action = latest.get("price_action", False)
    ema_cross = latest.get("ema_cross", False)

    raw_score = 0.0
    breakdown = {}

    weights = {
        "RSI": 1.0,
        "MACD": 1.2,
        "EMA_CROSS": 1.2,
        "Volume": 0.5,
        "HTF": 0.5,
        "PriceAction": 0.5,
    }

    # Пример: защита от NaN для rsi
    if not math.isnan(rsi) and 0 < rsi < 100 and (rsi < 35 or rsi > 65):
        raw_score += weights["RSI"]
        breakdown["RSI"] = weights["RSI"]

    # MACD выше сигнала?
    if macd > macd_signal:
        raw_score += weights["MACD"]
        breakdown["MACD"] = weights["MACD"]

    # EMA пересечение
    if ema_cross:
        raw_score += weights["EMA_CROSS"]
        breakdown["EMA_CROSS"] = weights["EMA_CROSS"]

    # Объёмный всплеск
    if volume_spike:
        raw_score += weights["Volume"]
        breakdown["Volume"] = weights["Volume"]

    # Тренд по старшему ТФ
    if htf_trend:
        raw_score += weights["HTF"]
        breakdown["HTF"] = weights["HTF"]

    # PriceAction (крупная свеча)
    if price_action:
        raw_score += weights["PriceAction"]
        breakdown["PriceAction"] = weights["PriceAction"]

    # Добавляем логи
    if breakdown:
        log(f"[ScoreDebug] {symbol} raw_score={raw_score:.2f}, breakdown={breakdown}", level="DEBUG")
    else:
        log(f"[ScoreDebug] {symbol} has no active signals ⇒ score=0", level="INFO")

    final_score = round(raw_score, 2)
    return final_score, breakdown


def explain_score(df):
    """
    Explains factors influencing the score in human-readable format.
    Enhanced with new short-term indicators.
    """
    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    macd = df["macd"].iloc[-1]
    signal = df["macd_signal"].iloc[-1]
    htf_trend = df.get("htf_trend", [False])[-1]

    parts = []
    # RSI signals
    if rsi < 30 or rsi > 70:
        parts.append("✅ RSI extreme zone")
    # MACD signals
    if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
        parts.append("✅ MACD/RSI aligned")
    if (macd > signal and price > ema) or (macd < signal and price < ema):
        parts.append("✅ Price/MACD vs EMA aligned")
    # Higher timeframe confirmation
    if htf_trend and price > ema:
        parts.append("✅ HTF trend confirmed")
    # Volume signals
    if df["volume"].iloc[-1] > df["volume"].mean():
        parts.append("✅ Volume above average")

    # NEW: EMA crossover
    if "fast_ema" in df.columns and "slow_ema" in df.columns:
        has_crossover, direction = detect_ema_crossover(df)
        if has_crossover and direction > 0:
            parts.append("✅ Recent bullish EMA crossover")
        elif has_crossover and direction < 0:
            parts.append("✅ Recent bearish EMA crossover")

    # NEW: Volume spike
    if detect_volume_spike(df):
        parts.append("✅ Volume spike detected")

    # NEW: Price action
    if len(df) >= 3:
        last_candle_size = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
        avg_candle_size = abs(df["close"].iloc[-6:-1] - df["open"].iloc[-6:-1]).mean()

        if last_candle_size > avg_candle_size * 1.5:
            if df["close"].iloc[-1] > df["open"].iloc[-1]:
                parts.append("✅ Strong bullish candle")
            else:
                parts.append("✅ Strong bearish candle")

    return "\n".join(parts) if parts else "❌ No significant signals"


def get_last_score_breakdown(symbol=None):
    """
    Returns detailed information about the last calculated score.
    """
    with last_score_lock:
        if not last_score_data:
            return None
        if symbol:
            return last_score_data.get(symbol)
        return max(last_score_data.values(), key=lambda x: x["timestamp"], default=None)


def update_signal_performance(signal_type, win):
    """
    New function: Track performance of different signal types
    to adaptively learn which signals work best.
    """
    global signal_performance

    if signal_type in signal_performance:
        if win:
            signal_performance[signal_type]["wins"] += 1
        else:
            signal_performance[signal_type]["losses"] += 1


def get_signal_winrate(signal_type):
    """
    New function: Calculate win rate for a specific signal type.
    """
    if signal_type not in signal_performance:
        return 0.5  # Default 50% if no data

    wins = signal_performance[signal_type]["wins"]
    losses = signal_performance[signal_type]["losses"]

    if wins + losses == 0:
        return 0.5

    return wins / (wins + losses)
