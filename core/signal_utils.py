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
    """
    Анализирует последние данные и возвращает направление ("buy"/"sell") и структуру сигнала.
    Добавлены DEBUG-логи + fallback-направление при сильных сигналах.
    """
    from utils_core import get_runtime_config
    from utils_logging import log

    if len(df) < 2:
        log("[SignalBreakdown] ❌ Not enough data for signal evaluation", level="WARNING")
        return None, {}

    latest = df.iloc[-1]
    cfg = get_runtime_config()
    rsi_threshold = cfg.get("rsi_threshold", 50)

    # MACD
    macd_val = latest.get("macd_5m", 0)
    macd_sig = latest.get("macd_signal_5m", 0)
    macd_signal = 1 if macd_val > macd_sig else 0
    macd_strength = abs(macd_val - macd_sig)

    # EMA Cross
    ema_cross_flag = 1 if latest.get("ema_cross", False) else 0

    # RSI
    rsi_val = latest.get("rsi_15m", 0)
    rsi_signal = 1 if rsi_val > rsi_threshold else 0
    rsi_strength = abs(rsi_val - 50)

    # Volume Spike
    vol_signal = 1 if latest.get("volume_spike", False) else 0

    # Price Action
    pa_signal = 1 if latest.get("price_action", False) else 0

    # HTF Trend
    htf_signal = 1 if latest.get("htf_trend", False) else 0

    breakdown = {
        "MACD": macd_signal,
        "EMA_CROSS": ema_cross_flag,
        "RSI": rsi_signal,
        "Volume": vol_signal,
        "PriceAction": pa_signal,
        "HTF": htf_signal,
        "strong_signal": ema_cross_flag and rsi_signal and vol_signal,
        "macd_strength": round(macd_strength, 4),
        "rsi_strength": round(rsi_strength, 2),
    }

    # === Направление
    direction = None

    # 1️⃣ Строгая логика
    if macd_val > macd_sig and ema_cross_flag:
        direction = "buy"
    elif macd_val < macd_sig and not ema_cross_flag:
        direction = "sell"
    else:
        # 2️⃣ Fallback: MACD override
        macd_override = cfg.get("macd_strength_override", 2.5)
        if macd_val > macd_sig and macd_strength >= macd_override:
            direction = "buy"
        elif macd_val < macd_sig and macd_strength >= macd_override:
            direction = "sell"
        else:
            # 3️⃣ Fallback: RSI экстремум
            if rsi_val > 60:
                direction = "buy"
            elif rsi_val < 40:
                direction = "sell"

    log(
        f"[SignalBreakdown] dir={direction} | "
        f"macd=({macd_val:.4f} vs {macd_sig:.4f}) | "
        f"ema_cross={ema_cross_flag} | "
        f"rsi={rsi_val:.2f} vs thresh={rsi_threshold} → rsi_sig={rsi_signal} | "
        f"vol_spike={vol_signal} | PA={pa_signal} | HTF={htf_signal}",
        level="DEBUG",
    )
    log(f"[SignalStrength] MACD Δ={macd_strength:.4f} | RSI Δ={rsi_strength:.2f}", level="DEBUG")
    log(f"[SignalBreakdown] breakdown={breakdown}", level="DEBUG")

    return direction, breakdown


def passes_1plus1(breakdown):
    """
    Проверка сигнала по логике 1+1 с комбинированной стратегией:
    - вход при ≥2 primary ИЛИ ≥1 primary + ≥1 secondary
    - вход при сильном MACD/RSI, даже если только один PRIMARY
    - отклоняется, если только один SECONDARY
    """
    config = get_runtime_config()
    mode = config.get("passes_1plus1_mode", "hybrid_strict")
    min_primary = config.get("min_primary_score", 2)
    min_secondary = config.get("min_secondary_score", 1)

    enable_override = config.get("enable_strong_signal_override", True)
    macd_override = config.get("macd_strength_override", 2.0)
    rsi_override = config.get("rsi_strength_override", 20)

    primary_components = {
        "MACD": int(breakdown.get("MACD", 0) or 0),
        "EMA_CROSS": int(breakdown.get("EMA_CROSS", 0) or 0),
        "RSI": int(breakdown.get("RSI", 0) or 0),
    }
    primary_sum = sum(primary_components.values())

    secondary_components = {
        "Volume": int(breakdown.get("Volume", 0) or 0),
        "PriceAction": int(breakdown.get("PriceAction", 0) or 0),
        "HTF": int(breakdown.get("HTF", 0) or 0),
    }
    secondary_sum = sum(secondary_components.values())

    macd_strength = breakdown.get("macd_strength", 0)
    rsi_strength = breakdown.get("rsi_strength", 0)

    if primary_sum == 0 and secondary_sum == 0:
        log("[1plus1] ❌ All components zero for signal → reject", level="DEBUG")
        return False

    # === Основная логика ===
    result = primary_sum >= min_primary or (primary_sum >= 1 and secondary_sum >= min_secondary)

    # === Допуск при одном MACD или RSI с силой
    if not result and primary_sum == 1 and secondary_sum == 0:
        if macd_strength > 0.0012 or rsi_strength > 1.0:
            result = True
            log("[1plus1] 🔓 Permissive pass: 1 strong primary without secondary", level="DEBUG")

    # === Override (сильный макд или рси)
    if not result and enable_override:
        if macd_strength >= macd_override or rsi_strength >= rsi_override:
            result = True
            log(
                f"[1plus1] 🚨 Strong signal override: macd_strength={macd_strength:.2f}, rsi_strength={rsi_strength:.2f} → ✅ OVERRIDE PASS",
                level="DEBUG",
            )
        else:
            log(
                f"[1plus1] ⛔ Override check failed: macd={macd_strength:.2f}, rsi={rsi_strength:.2f} (thresholds: {macd_override}/{rsi_override})",
                level="DEBUG",
            )

    log(
        f"[1plus1] ➕ PRIMARY: {primary_components} = {primary_sum} | "
        f"🔧 SECONDARY: {secondary_components} = {secondary_sum} | "
        f"🧠 Mode={mode} | ✅ RESULT: {result}",
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
            log(f"[Filter] {symbol} ❌ rsi_15m={latest.get('rsi_15m', 0):.2f} < {rsi_thr}", level="DEBUG")
            return False

        if rel_volume < vol_thr:
            log(f"[Filter] {symbol} ❌ rel_volume_15m={rel_volume:.3f} < {vol_thr}", level="DEBUG")
            return False

        if atr_pct < atr_thr_pct:
            log(f"[Filter] {symbol} ❌ atr_pct={atr_pct:.5f} < {atr_thr_pct}", level="DEBUG")
            return False

        if volume_usdt < vol_abs_min:
            log(f"[Filter] {symbol} ❌ volume_usdt={volume_usdt:.1f} < {vol_abs_min}", level="DEBUG")
            return False

        return True

    except Exception as e:
        log(f"[Filter] {symbol} error: {e}", level="ERROR")
        return False
