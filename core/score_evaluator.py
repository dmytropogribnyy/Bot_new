# score_evaluator.py
import threading
from datetime import datetime

import pytz
from score_logger import log_score_components

from common.config_loader import (
    ADAPTIVE_SCORE_ENABLED,
    DRY_RUN,
    PRIORITY_SMALL_BALANCE_PAIRS,
    SCORE_WEIGHTS,
)
from utils_core import get_runtime_config
from utils_logging import log

last_score_data = {}
last_score_lock = threading.Lock()
# Track win/loss by signal type for adaptive learning
signal_performance = {
    "RSI": {"wins": 0, "losses": 0},
    "MACD_RSI": {"wins": 0, "losses": 0},
    "MACD_EMA": {"wins": 0, "losses": 0},
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
    elif balance < 250:
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
    if balance < 150 and symbol and symbol.split("/")[0] in ["XRP", "DOGE", "ADA", "MATIC", "DOT"]:
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
    if balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
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
    elif balance < 150:
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
    if balance and balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
        base_rr *= 0.6  # 40% скидка вместо 10%

    # Дополнительная скидка для очень малых депозитов
    if balance and balance < 100:
        base_rr *= 0.8  # Ещё 20% скидка для депозитов <100 USDC

    return base_rr


def detect_ema_crossover(df):
    """
    New function: Detect recent EMA crossover for short-term momentum signals.
    """
    if "fast_ema" not in df.columns or "slow_ema" not in df.columns:
        return False, 0

    # Check if we have a recent crossover (within last 3 candles)
    fast_ema = df["fast_ema"].iloc[-3:].values
    slow_ema = df["slow_ema"].iloc[-3:].values

    # Check for bullish crossover (fast crosses above slow)
    if fast_ema[-1] > slow_ema[-1] and fast_ema[-3] <= slow_ema[-3]:
        return True, 1  # Bullish

    # Check for bearish crossover (fast crosses below slow)
    if fast_ema[-1] < slow_ema[-1] and fast_ema[-3] >= slow_ema[-3]:
        return True, -1  # Bearish

    return False, 0


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
    from symbol_activity_tracker import load_activity
    from utils_core import get_cached_balance, get_runtime_config

    config = get_runtime_config()
    use_multi = config.get("USE_MULTITF_LOGIC", False)
    rsi_threshold = config.get("rsi_threshold", 50)

    raw_score = 0.0
    latest = df.iloc[-1]
    price = latest["close"]
    ema = latest.get("ema") or latest.get("ema_15m") or 0
    balance = get_cached_balance()

    score_weights = SCORE_WEIGHTS.copy()
    score_weights.setdefault("EMA_CROSS", 2.0)
    score_weights.setdefault("VOL_SPIKE", 1.5)
    score_weights.setdefault("PRICE_ACTION", 1.5)

    max_raw_score = sum(score_weights.values())

    breakdown = {
        "RSI": 0,
        "MACD_RSI": 0,
        "MACD_EMA": 0,
        "HTF": 0,
        "VOLUME": 0,
        "EMA_CROSS": 0,
        "VOL_SPIKE": 0,
        "PRICE_ACTION": 0,
    }

    if use_multi:
        for tf in ["rsi_3m", "rsi_5m", "rsi_15m"]:
            if latest.get(tf, 0) > rsi_threshold:
                raw_score += 0.5
                breakdown["RSI"] += 0.5

        if latest.get("macd_5m", 0) > latest.get("macd_signal_5m", 9999):
            raw_score += 1.0
            breakdown["MACD_EMA"] = 1.0

        if latest.get("atr_15m", 0) > 0:
            raw_score += 0.5
            breakdown["VOLUME"] = 0.5

    else:
        rsi = latest["rsi"]
        macd = latest["macd"]
        signal = latest["macd_signal"]
        htf_trend = latest.get("htf_trend", False)

        rsi_lo, rsi_hi = (30, 70)
        if ADAPTIVE_SCORE_ENABLED:
            if price > ema:
                rsi_lo, rsi_hi = (35, 75)
            else:
                rsi_lo, rsi_hi = (25, 65)

        if rsi < rsi_lo or rsi > rsi_hi:
            raw_score += score_weights["RSI"]
            breakdown["RSI"] = score_weights["RSI"]

        if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
            raw_score += score_weights["MACD_RSI"]
            breakdown["MACD_RSI"] = score_weights["MACD_RSI"]

        if (macd > signal and price > ema) or (macd < signal and price < ema):
            raw_score += score_weights["MACD_EMA"]
            breakdown["MACD_EMA"] = score_weights["MACD_EMA"]

        if htf_trend and price > ema:
            raw_score += score_weights["HTF"]
            breakdown["HTF"] = score_weights["HTF"]

        avg_volume = df["volume"].mean()
        if latest["volume"] > avg_volume:
            raw_score += score_weights["VOLUME"]
            breakdown["VOLUME"] = score_weights["VOLUME"]

    # Active symbol bonus
    activity_data = load_activity()
    recent_count = len(activity_data.get(symbol, []))
    if recent_count >= 3:
        raw_score += 0.2
        breakdown["Activity"] = 0.2
        log(f"{symbol} 🔔 Active symbol bonus: {recent_count} signals (score +0.2)", level="DEBUG")

    has_crossover, direction = detect_ema_crossover(df)
    if has_crossover and ((direction > 0 and price > ema) or (direction < 0 and price < ema)):
        raw_score += score_weights["EMA_CROSS"]
        breakdown["EMA_CROSS"] = score_weights["EMA_CROSS"]

    if detect_volume_spike(df, lookback=5, threshold=1.5):
        raw_score += score_weights["VOL_SPIKE"]
        breakdown["VOL_SPIKE"] = score_weights["VOL_SPIKE"]

    if len(df) >= 6:
        last_size = abs(latest["close"] - latest["open"])
        avg_size = abs(df["close"].iloc[-6:-1] - df["open"].iloc[-6:-1]).mean()
        if last_size > avg_size * 1.5:
            if (latest["close"] > latest["open"] and price > ema) or (latest["close"] < latest["open"] and price < ema):
                raw_score += score_weights["PRICE_ACTION"]
                breakdown["PRICE_ACTION"] = score_weights["PRICE_ACTION"]

    normalized_score = (raw_score / max_raw_score) * 5
    final_score = round(normalized_score, 1)

    atr = latest.get("atr") or latest.get("atr_15m") or 0
    market_volatility = "medium"
    if atr and price:
        atr_pct = atr / price
        if atr_pct > 0.018:
            market_volatility = "high"
        elif atr_pct < 0.005:
            market_volatility = "low"

    min_score = get_adaptive_min_score(balance, market_volatility, symbol)

    with last_score_lock:
        last_score_data[symbol] = {
            "symbol": symbol,
            "total": final_score,
            "details": breakdown,
            "threshold": min_score,
            "final": final_score >= min_score,
            "timestamp": datetime.utcnow(),
            "market_volatility": market_volatility,
        }

    log_score_components(symbol, final_score, breakdown)

    if DRY_RUN:
        log(
            f"{symbol or ''} 📊 Score: {final_score:.1f}/5 (raw: {raw_score:.2f}/{max_raw_score:.1f}), " f"Min required: {min_score:.1f}, Market volatility: {market_volatility}",
            level="DEBUG",
        )

    return final_score


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
