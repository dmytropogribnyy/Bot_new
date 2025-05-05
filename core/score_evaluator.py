# score_evaluator.py
import threading
from datetime import datetime

from common.config_loader import (
    ADAPTIVE_SCORE_ENABLED,
    DRY_RUN,
    SCORE_WEIGHTS,
)
from utils_logging import log

last_score_data = {}
last_score_lock = threading.Lock()


def get_adaptive_min_score(balance, market_volatility=None):
    """
    Возвращает адаптивный минимальный score на основе размера счета и волатильности рынка.

    Args:
        balance: Размер депозита
        market_volatility: Оценка общей волатильности рынка (high/medium/low)

    Returns:
        Минимальный score для входа в сделку
    """
    # Базовый минимальный score в зависимости от баланса
    if balance < 100:
        base_threshold = 2.5  # Снижено для маленьких депозитов
    elif balance < 200:
        base_threshold = 3.0
    else:
        base_threshold = 3.5

    # Корректировка на волатильность рынка
    if market_volatility == "high":
        # В высоковолатильном рынке снижаем требования - больше сигналов
        return max(2.0, base_threshold - 0.5)
    elif market_volatility == "low":
        # В низковолатильном рынке повышаем требования - меньше ложных сигналов
        return base_threshold + 0.5

    return base_threshold


def get_risk_percent_by_score(balance, score):
    """
    Адаптивный процент риска на основе score и размера счета.

    Args:
        balance: Размер депозита
        score: Оценка качества сигнала (1-5)

    Returns:
        Процент риска для данной сделки
    """
    from utils_core import get_adaptive_risk_percent

    # Получаем базовый риск в зависимости от размера счета
    base_risk = get_adaptive_risk_percent(balance)

    # Корректируем риск в зависимости от score
    if score < 3.0:
        risk = base_risk * 0.5  # 50% от базового риска для слабых сигналов
    elif score < 3.5:
        risk = base_risk * 0.75  # 75% от базового риска для средних сигналов
    elif score < 4.0:
        risk = base_risk  # 100% от базового риска для хороших сигналов
    else:
        risk = min(base_risk * 1.2, 0.02)  # 120% от базового риска для отличных сигналов, но не более 2%

    # Дополнительное ограничение для очень маленьких депозитов
    if balance < 100:
        risk = min(risk, 0.01)  # Не более 1% для депозитов менее 100 USDC

    return risk


def get_required_risk_reward_ratio(score):
    """
    Возвращает минимальное требуемое соотношение риск/прибыль в зависимости от score.

    Args:
        score: Оценка качества сигнала (1-5)

    Returns:
        Минимальное соотношение риск/прибыль
    """
    if score < 3.0:
        return 2.0  # Для слабых сигналов требуем соотношение 1:2
    elif score < 3.5:
        return 1.7  # Для средних сигналов требуем соотношение 1:1.7
    elif score < 4.0:
        return 1.5  # Для хороших сигналов требуем соотношение 1:1.5
    else:
        return 1.3  # Для отличных сигналов требуем соотношение 1:1.3


def calculate_score(df, symbol=None, trade_count=0, winrate=0.0):
    """
    Вычисляет итоговый score на основе взвешенной системы показателей с нормализацией до 0–5.

    Args:
        df (pd.DataFrame): Данные с индикаторами.
        symbol (str, optional): Символ для логирования.
        trade_count (int): Количество сделок (для расчёта порога).
        winrate (float): Винрейт (для расчёта порога).
    """
    from utils_core import get_cached_balance

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

    # Получаем текущий баланс
    balance = get_cached_balance()

    # Определяем волатильность рынка (можно реализовать более сложную логику)
    market_volatility = "medium"
    if "atr" in df.columns and not df["atr"].empty:
        atr_pct = df["atr"].iloc[-1] / price
        if atr_pct > 0.02:  # 2% ATR считаем высокой волатильностью
            market_volatility = "high"
        elif atr_pct < 0.005:  # 0.5% ATR считаем низкой волатильностью
            market_volatility = "low"

    # Получаем минимальный порог на основе баланса и волатильности
    min_score = get_adaptive_min_score(balance, market_volatility)

    # Логирование деталей score
    with last_score_lock:
        last_score_data[symbol] = {
            "symbol": symbol,
            "total": final_score,
            "details": breakdown,
            "threshold": min_score,
            "final": final_score >= min_score,
            "timestamp": datetime.utcnow(),
        }

    if DRY_RUN:
        log(
            f"{symbol or ''} 📊 Score: {final_score:.1f}/5 (raw: {raw_score:.2f}/{max_raw_score:.1f}), " f"Min required: {min_score:.1f}, Market volatility: {market_volatility}",
            level="DEBUG",
        )

    return final_score


def explain_score(df):
    """
    Объясняет факторы, повлиявшие на расчет score, в человекочитаемом виде.
    """
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
    """
    Возвращает детальную информацию о последнем рассчитанном score.

    Args:
        symbol: Символ пары (если None, возвращает самый последний для любой пары)

    Returns:
        Словарь с информацией о score или None
    """
    with last_score_lock:
        if not last_score_data:
            return None
        if symbol:
            return last_score_data.get(symbol)
        return max(last_score_data.values(), key=lambda x: x["timestamp"], default=None)
