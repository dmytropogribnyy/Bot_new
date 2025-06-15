# signal_utils.py
import pandas as pd
import ta

from utils_core import get_runtime_config  # Добавить в начало файла, если ещё не импортирован
from utils_logging import log


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
    if len(df) < 2:
        return None, {}

    latest = df.iloc[-1]
    cfg = get_runtime_config()
    rsi_threshold = cfg.get("rsi_threshold", 50)

    # MACD
    macd_val = latest.get("macd_5m", 0)
    macd_sig = latest.get("macd_signal_5m", 0)
    macd_signal = 1 if macd_val > macd_sig else 0

    # EMA Cross
    ema_cross_flag = 1 if latest.get("ema_cross", False) else 0

    # RSI
    rsi_val = latest.get("rsi_15m", 0)
    rsi_signal = 1 if rsi_val > rsi_threshold else 0

    # Volume Spike
    vol_signal = 1 if latest.get("volume_spike", False) else 0

    # PriceAction
    pa_signal = 1 if latest.get("price_action", False) else 0

    # HTF Trend
    htf_signal = 0
    if "htf_trend" in df.columns:
        htf_signal = 1 if bool(latest.get("htf_trend", False)) else 0

    breakdown = {
        "MACD": macd_signal,
        "EMA_CROSS": ema_cross_flag,
        "RSI": rsi_signal,
        "Volume": vol_signal,
        "PriceAction": pa_signal,
        "HTF": htf_signal,
        "strong_signal": ema_cross_flag and rsi_signal and vol_signal,
    }

    # === Определение направления
    direction = None
    if macd_val > macd_sig and ema_cross_flag:
        direction = "buy"
    elif macd_val < macd_sig and not ema_cross_flag:
        direction = "sell"

    return direction, breakdown


def passes_1plus1(breakdown):
    """
    Адаптивная проверка сигнала по модели 1+1:
    - PRIMARY: MACD, EMA_CROSS, RSI
    - SECONDARY: Volume, PriceAction, HTF

    Условия (по runtime_config):
    - soft_mode = True: (PRIMARY ≥ X and SECONDARY ≥ Y) or (PRIMARY ≥ 1)
    - soft_mode = False: строго PRIMARY ≥ X and SECONDARY ≥ Y
    - автоматическое усиление, если все компоненты 0
    """
    config = get_runtime_config()
    soft_mode = config.get("enable_passes_1plus1_soft", True)
    min_primary = config.get("min_primary_score", 1)
    min_secondary = config.get("min_secondary_score", 1)

    # PRIMARY компоненты: индикаторы направления
    primary_components = {
        "MACD": breakdown.get("MACD", 0),
        "EMA_CROSS": breakdown.get("EMA_CROSS", 0),
        "RSI": breakdown.get("RSI", 0),
    }
    primary_sum = sum(primary_components.values())

    # SECONDARY компоненты: подтверждающие сигналы
    secondary_components = {
        "Volume": breakdown.get("Volume", 0),
        "PriceAction": breakdown.get("PriceAction", 0),
        "HTF": breakdown.get("HTF", 0),
    }
    secondary_sum = sum(secondary_components.values())

    # Дополнительная гибкость: если всё = 0, считаем сразу фейл
    if primary_sum == 0 and secondary_sum == 0:
        log("[1plus1] ❌ All components zero for signal → reject", level="DEBUG")
        return False

    # Гибкая логика прохода
    if soft_mode:
        result = (primary_sum >= min_primary and secondary_sum >= min_secondary) or (primary_sum >= 1)
    else:
        result = primary_sum >= min_primary and secondary_sum >= min_secondary

    log(
        f"[1plus1] ➕ PRIMARY: {primary_components} = {primary_sum} | " f"🔧 SECONDARY: {secondary_components} = {secondary_sum} | " f"✅ RESULT: {result}",
        level="DEBUG",
    )

    return result


def add_indicators(df):
    """
    Добавляет ключевые индикаторы: ATR%, MACD, RSI, EMA.
    Предполагается, что df содержит колонки: open, high, low, close, volume.
    """
    import pandas as pd
    import ta

    try:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return df

        # ATR%
        atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()
        df["atr"] = atr
        df["atr_percent"] = atr / df["close"]

        # MACD
        macd_ind = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd_5m"] = macd_ind.macd()
        df["macd_signal_5m"] = macd_ind.macd_signal()

        # RSI
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

        # EMA 21/55
        df["ema_21"] = df["close"].ewm(span=21).mean()
        df["ema_55"] = df["close"].ewm(span=55).mean()

        return df

    except Exception as e:
        log(f"[Indicators] Failed to add indicators: {e}", level="ERROR")
        return df


def passes_filters(df: pd.DataFrame, symbol: str) -> bool:
    """
    Фильтры по RSI, относительному и абсолютному объёму, ATR%:
    - rsi_15m >= threshold
    - rel_volume_15m >= threshold
    - atr_15m / price >= atr_threshold_percent
    - volume_usdt >= volume_threshold_usdc
    """
    try:
        config = get_runtime_config()
        rsi_thr = config.get("rsi_threshold", 50)
        vol_thr = config.get("rel_volume_threshold", 0.3)
        atr_thr_pct = config.get("atr_threshold_percent", 0.0015)
        vol_abs_min = config.get("volume_threshold_usdc", 600)

        latest = df.iloc[-1]
        close = latest.get("close", 0)
        atr = latest.get("atr_15m", 0)
        atr_pct = atr / close if close > 0 else 0
        rel_volume = latest.get("rel_volume_15m", 0)
        volume_usdt = latest.get("volume_usdt_15m", 0)

        if latest.get("rsi_15m", 0) < rsi_thr:
            log(f"[Filter] {symbol} ❌ rsi_15m < {rsi_thr}", level="DEBUG")
            return False

        if rel_volume < vol_thr:
            log(f"[Filter] {symbol} ❌ rel_volume_15m < {vol_thr}", level="DEBUG")
            return False

        if atr_pct < atr_thr_pct:
            log(f"[Filter] {symbol} ❌ atr_pct {atr_pct:.5f} < {atr_thr_pct}", level="DEBUG")
            return False

        if volume_usdt < vol_abs_min:
            log(f"[Filter] {symbol} ❌ volume_usdt {volume_usdt:.1f} < {vol_abs_min}", level="DEBUG")
            return False

        return True

    except Exception as e:
        log(f"[Filter] {symbol} error: {e}", level="ERROR")
        return False
