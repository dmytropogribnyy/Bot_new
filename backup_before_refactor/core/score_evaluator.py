# score_evaluator.py
import threading
import time
from datetime import datetime

import pandas as pd

from utils_logging import log

last_score_data = {}
last_score_lock = threading.Lock()


def get_adaptive_min_score(trade_count, winrate):
    # Move imports inside the function
    from config import EXPORT_PATH
    from utils_core import get_cached_balance

    balance = get_cached_balance()

    # Адаптация base в зависимости от депозита
    if balance < 100:
        base = 2.0  # Смягчаем для депозита < 100 долларов
    elif 100 <= balance < 500:
        base = 2.25
    elif 500 <= balance < 1000:
        base = 2.5
    else:
        base = 2.0  # Для депозита ≥ 1000 долларов

    if trade_count < 20:
        threshold = base + 0.25  # Уменьшаем влияние trade_count
    else:
        threshold = base - (winrate - 0.5) * 1.0  # Влияние winrate ±0.5

    # Корректировка на основе частоты сделок
    if trade_count > 0:
        try:
            df = pd.read_csv(EXPORT_PATH)
            if not df.empty:
                days = (time.time() - pd.to_datetime(df["Date"]).min().timestamp()) / (24 * 60 * 60)
                trades_per_day = trade_count / max(days, 1)
                if trades_per_day < 1:
                    threshold -= 0.25  # Смягчаем, если сделок мало
                elif trades_per_day > 5:
                    threshold += 0.25  # Ужесточаем, если сделок много
        except Exception as e:
            log(f"[ERROR] Failed to calculate trades per day: {e}")

    return max(threshold, base - 0.5)  # Минимальный порог


def calculate_score(df, symbol=None, trade_count=0, winrate=0.0):
    """
    Вычисляет итоговый score на основе взвешенной системы показателей с нормализацией до 0–5.

    Args:
        df (pd.DataFrame): Данные с индикаторами.
        symbol (str, optional): Символ для логирования.
        trade_count (int): Количество сделок (для расчёта порога).
        winrate (float): Винрейт (для расчёта порога).
    """
    # Move imports inside the function
    from config import ADAPTIVE_SCORE_ENABLED, DRY_RUN, SCORE_WEIGHTS

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
        "VOLUME": 0,
    }

    # Адаптивные пороги RSI в зависимости от тренда
    rsi_lo, rsi_hi = (35, 65)
    if ADAPTIVE_SCORE_ENABLED:
        if price > ema:
            rsi_lo, rsi_hi = (40, 70)
        else:
            rsi_lo, rsi_hi = (30, 60)

    # RSI: +1 если RSI в зоне перепроданности/перекупленности
    if rsi < rsi_lo or rsi > rsi_hi:
        raw_score += score_weights["RSI"]
        breakdown["RSI"] = score_weights["RSI"]

    # MACD/RSI: +1 если MACD подтверждает RSI
    if (macd > signal and rsi < 50) or (macd < signal and rsi > 50):
        raw_score += score_weights["MACD_RSI"]
        breakdown["MACD_RSI"] = score_weights["MACD_RSI"]

    # MACD/EMA: +1 если MACD подтверждает тренд по EMA
    if (macd > signal and price > ema) or (macd < signal and price < ema):
        raw_score += score_weights["MACD_EMA"]
        breakdown["MACD_EMA"] = score_weights["MACD_EMA"]

    # HTF: +1 если тренд на старшем таймфрейме подтверждает
    if htf_trend and price > ema:
        raw_score += score_weights["HTF"]
        breakdown["HTF"] = score_weights["HTF"]

    # Объём: +0.5 если объём выше среднего
    avg_volume = df["volume"].mean()
    if df["volume"].iloc[-1] > avg_volume:
        raw_score += score_weights["VOLUME"]
        breakdown["VOLUME"] = score_weights["VOLUME"]

    # Нормализация score до 0–5
    normalized_score = (raw_score / max_raw_score) * 5
    final_score = round(normalized_score, 1)

    # Логирование деталей score
    with last_score_lock:
        last_score_data[symbol] = {
            "symbol": symbol,
            "total": final_score,
            "details": breakdown,
            "threshold": get_adaptive_min_score(trade_count, winrate),
            "final": final_score >= get_adaptive_min_score(trade_count, winrate),
            "timestamp": datetime.utcnow(),
        }

    if DRY_RUN:
        log(
            f"{symbol or ''} 📊 Score: {final_score:.1f}/5 (raw: {raw_score:.2f}/{max_raw_score:.1f})",
            level="DEBUG",
        )

    return final_score


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
    if df["volume"].iloc[-1] > df["volume"].mean():
        parts.append("✅ Volume above average")

    return "\n".join(parts) if parts else "❌ No significant signals"


def get_last_score_breakdown(symbol=None):
    with last_score_lock:
        if not last_score_data:
            return None
        if symbol:
            return last_score_data.get(symbol)
        return max(last_score_data.values(), key=lambda x: x["timestamp"], default=None)
