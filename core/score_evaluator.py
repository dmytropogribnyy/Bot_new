# score_evaluator.py — адаптивный модуль расчёта сигнального score с весами и нормализацией

import threading
from datetime import datetime

from config import ADAPTIVE_SCORE_ENABLED, DRY_RUN, MIN_TRADE_SCORE, SCORE_WEIGHTS
from utils_logging import log

last_score_data = {}
last_score_lock = threading.Lock()


def calculate_score(df, symbol=None):
    """
    Вычисляет итоговый score на основе взвешенной системы показателей с нормализацией до 0–5.
    """
    raw_score = 0.0
    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    macd = df["macd"].iloc[-1]
    signal = df["macd_signal"].iloc[-1]
    htf_trend = df.get("htf_trend", [False])[-1]

    score_weights = SCORE_WEIGHTS
    max_raw_score = sum(score_weights.values())

    breakdown = {
        "RSI": 0,
        "MACD_RSI": 0,
        "MACD_EMA": 0,
        "HTF": 0,
    }

    rsi_lo, rsi_hi = (35, 65)
    if ADAPTIVE_SCORE_ENABLED:
        if price > ema:
            rsi_lo, rsi_hi = 40, 70
        else:
            rsi_lo, rsi_hi = 30, 60

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

    normalized_score = (raw_score / max_raw_score) * 5
    final_score = round(normalized_score, 1)

    with last_score_lock:
        last_score_data[symbol] = {
            "symbol": symbol,
            "total": final_score,
            "details": breakdown,
            "threshold": MIN_TRADE_SCORE,
            "final": final_score >= MIN_TRADE_SCORE,
            "timestamp": datetime.utcnow(),
        }

    if DRY_RUN:
        log(
            f"{symbol or ''} 📊 Score: {final_score:.1f}/5 (raw: {raw_score:.2f}/{max_raw_score:.1f})",
            level="DEBUG",
        )

    return final_score


def get_adaptive_min_score(trade_count, winrate):
    base = 3.0
    if trade_count < 20:
        return base + 0.5  # Строгий порог для малого числа сделок
    return base - (winrate - 0.5) * 0.5  # Адаптация по винрейту


def explain_score(df):
    price = df["close"].iloc[-1]
    ema = df["ema"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    macd = df["macd"].iloc[-1]
    signal = df["macd_signal"].iloc[-1]
    htf_trend = df.get("htf_trend", [False])[-1]

    parts = []
    if rsi < 35 or rsi > 65:
        parts.append("✅ RSI extreme")
    if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
        parts.append("✅ MACD/RSI aligned")
    if (macd > signal and price > ema) or (macd < signal and price < ema):
        parts.append("✅ Price/MACD vs EMA aligned")
    if htf_trend and price > ema:
        parts.append("✅ HTF trend confirmed")

    return "\n".join(parts)


def get_last_score_breakdown(symbol=None):
    with last_score_lock:
        if not last_score_data:
            return None
        if symbol:
            return last_score_data.get(symbol)
        return max(last_score_data.values(), key=lambda x: x["timestamp"], default=None)
