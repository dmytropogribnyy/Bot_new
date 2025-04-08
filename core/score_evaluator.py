# score_evaluator.py — адаптивный модуль расчёта сигнального score

from config import ADAPTIVE_SCORE_ENABLED, DRY_RUN, MIN_TRADE_SCORE
from utils_logging import log


def calculate_score(df, symbol=None):
    """
    Вычисляет итоговый score по индикаторам с возможностью гибкой адаптации.
    """
    score = 0
    rsi = df["rsi"].iloc[-1]
    macd = df["macd"].iloc[-1]
    signal = df["macd_signal"].iloc[-1]
    ema = df["ema"].iloc[-1]
    price = df["close"].iloc[-1]
    htf_trend = df.get("htf_trend", [False])[-1]

    # Адаптивные границы RSI (если включено)
    rsi_lo, rsi_hi = (30, 70)
    if ADAPTIVE_SCORE_ENABLED:
        if price > ema:
            rsi_lo, rsi_hi = 35, 75
        else:
            rsi_lo, rsi_hi = 25, 65

    if rsi < rsi_lo or rsi > rsi_hi:
        score += 1
    if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
        score += 1
    if (macd > signal and price > ema) or (macd < signal and price < ema):
        score += 1
    if htf_trend and price > ema:
        score += 1

    if DRY_RUN:
        log(f"{symbol or ''} 📊 Score: {score}/5", level="DEBUG")

    return score


def get_adaptive_min_score(trade_count_last_days=0, winrate=0.0):
    """
    Возвращает адаптивный порог score в зависимости от накопленных данных.
    """
    if trade_count_last_days < 20:
        return max(MIN_TRADE_SCORE - 1, 1)  # мягкий старт
    if winrate < 0.4:
        return MIN_TRADE_SCORE - 1
    if winrate > 0.6:
        return MIN_TRADE_SCORE + 1
    return MIN_TRADE_SCORE


def explain_score(df):
    """
    Возвращает подробный breakdown score для Telegram-отчётов
    """
    rsi = df["rsi"].iloc[-1]
    macd = df["macd"].iloc[-1]
    signal = df["macd_signal"].iloc[-1]
    ema = df["ema"].iloc[-1]
    price = df["close"].iloc[-1]
    htf_trend = df.get("htf_trend", [False])[-1]

    components = []
    if rsi < 30 or rsi > 70:
        components.append("✅ RSI extreme")
    if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
        components.append("✅ MACD/RSI aligned")
    if (macd > signal and price > ema) or (macd < signal and price < ema):
        components.append("✅ Price/MACD vs EMA aligned")
    if htf_trend and price > ema:
        components.append("✅ HTF trend confirmed")

    return "\n".join(components)
