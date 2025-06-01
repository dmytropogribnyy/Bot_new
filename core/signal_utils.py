# signal_utils.py
import pandas as pd
import ta

from utils_core import log


def detect_ema_crossover(df, fast_window=9, slow_window=21):
    """
    Определяем пересечение EMA (быстрая / медленная).
    Возвращает (has_crossover, direction): bool и int (1 / -1 / 0).
    """
    try:
        fast = ta.trend.EMAIndicator(df["close"], fast_window).ema_indicator()
        slow = ta.trend.EMAIndicator(df["close"], slow_window).ema_indicator()

        if fast.iloc[-2] < slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]:
            return True, 1  # бычье пересечение
        elif fast.iloc[-2] > slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]:
            return True, -1  # медвежье пересечение
        return False, 0
    except Exception:
        return False, 0


def detect_volume_spike(df, lookback=5, threshold=1.5):
    """
    Проверяем всплеск объёма: текущий volume выше средней за lookback
    в threshold раз.
    """
    if len(df) < lookback + 1:
        return False

    recent_volume = df["volume"].iloc[-1]
    avg_volume = df["volume"].iloc[-(lookback + 1) : -1].mean()
    return bool(recent_volume > avg_volume * threshold)


def get_signal_breakdown(df):
    """
    Собираем бинарные сигналы (1/0) по MACD, EMA, RSI, Volume, PriceAction,
    и при наличии htf_trend.
    """
    if len(df) < 2:
        return {}

    latest = df.iloc[-1]

    # MACD
    macd_val = latest.get("macd_5m", 0)
    macd_sig = latest.get("macd_signal_5m", 0)
    macd_signal = 1 if macd_val > macd_sig else 0

    # EMA Cross (уже рассчитан в df["ema_cross"])
    ema_cross_flag = 1 if latest.get("ema_cross", False) else 0

    # RSI (например, если rsi_15m > 50, считаем за сигнал)
    rsi_val = latest.get("rsi_15m", 0)
    rsi_signal = 1 if rsi_val > 50 else 0

    # Volume Spike (df["volume_spike"] = True/False)
    vol_signal = 1 if latest.get("volume_spike", False) else 0

    # PriceAction (df["price_action"] = True/False)
    pa_signal = 1 if latest.get("price_action", False) else 0

    # HTF
    htf_signal = 0
    if "htf_trend" in df.columns:
        if bool(latest.get("htf_trend", False)):
            htf_signal = 1

    return {"MACD": macd_signal, "EMA_CROSS": ema_cross_flag, "RSI": rsi_signal, "Volume": vol_signal, "PriceAction": pa_signal, "HTF": htf_signal}


def passes_1plus1(breakdown):
    """
    Проверяем “1 основной + 1 дополнительный”:
    - Основные: MACD, EMA_CROSS, RSI
    - Дополнительные: Volume, PriceAction, HTF
    """
    primary = breakdown.get("MACD", 0) + breakdown.get("EMA_CROSS", 0) + breakdown.get("RSI", 0)
    secondary = breakdown.get("Volume", 0) + breakdown.get("PriceAction", 0) + breakdown.get("HTF", 0)
    return (primary >= 1) and (secondary >= 1)


def add_indicators(df):
    # Приводим к DataFrame, если df — список
    if isinstance(df, list):
        df = pd.DataFrame(df, columns=["time", "open", "high", "low", "close", "volume"])

    try:
        df["atr_percent"] = ta.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=14).average_true_range() / df["close"]
        ...
    except Exception as e:
        log(f"[add_indicators] Ошибка: {e}", level="ERROR")

    return df
