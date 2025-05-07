# tp_utils.py

import pandas as pd

from common.config_loader import (
    AUTO_TP_SL_ENABLED,
    FLAT_ADJUSTMENT,
    SL_PERCENT,
    TP1_PERCENT,
    TP1_SHARE,
    TP2_PERCENT,
    TP2_SHARE,
    TREND_ADJUSTMENT,
)
from utils_logging import log


def calculate_tp_levels(entry_price: float, side: str, regime: str = None, score: float = 5, df=None):
    """
    Вычисляет цены TP1, TP2 и SL на основе ATR и цены входа.
    """
    # Проверка валидности входных данных
    if entry_price is None or entry_price <= 0:
        log(f"Ошибка: некорректная цена входа {entry_price}", level="ERROR")
        # Возвращаем безопасные дефолтные значения
        return None, None, None, TP1_SHARE, 0

    if side is None:
        log("Ошибка: side is None", level="ERROR")
        return None, None, None, TP1_SHARE, 0

    # Явная инициализация дефолтных значений
    tp1_pct = TP1_PERCENT
    tp2_pct = TP2_PERCENT
    sl_pct = SL_PERCENT

    # Используем ATR если доступен
    if df is not None and "atr" in df.columns and not df["atr"].empty:
        try:
            atr = df["atr"].iloc[-1]
            # Расширенная проверка на валидность ATR
            if atr is not None and not pd.isna(atr) and atr > 0:
                atr_pct = atr / entry_price

                # ATR-зависимые расчеты с минимальными порогами
                tp1_pct = max(atr_pct * 1.2, TP1_PERCENT)  # 20% increase
                tp2_pct = max(atr_pct * 2.4, TP2_PERCENT)  # 20% increase
                sl_pct = max(atr_pct * 0.8, SL_PERCENT)  # 47% decrease

                log(f"ATR-зависимый расчет TP/SL: ATR={atr:.6f}, TP1={tp1_pct:.4f}, TP2={tp2_pct:.4f}, SL={sl_pct:.4f}", level="DEBUG")
            else:
                log(f"ATR невалиден: {atr}, используем стандартные значения", level="WARNING")
                # Убедимся, что стандартные значения заданы
                tp1_pct = TP1_PERCENT
                tp2_pct = TP2_PERCENT
                sl_pct = SL_PERCENT
        except Exception as e:
            log(f"Ошибка расчета ATR-зависимых TP/SL: {e}", level="ERROR")
            # Убедимся, что стандартные значения заданы при ошибке
            tp1_pct = TP1_PERCENT
            tp2_pct = TP2_PERCENT
            sl_pct = SL_PERCENT

    # Применяем корректировки режима рынка
    if AUTO_TP_SL_ENABLED and regime:
        if regime == "flat":
            tp1_pct *= FLAT_ADJUSTMENT
            tp2_pct *= FLAT_ADJUSTMENT
            sl_pct *= FLAT_ADJUSTMENT
            log(f"Применена корректировка для бокового рынка: TP1={tp1_pct:.4f}, TP2={tp2_pct:.4f}, SL={sl_pct:.4f}", level="DEBUG")
        elif regime == "trend":
            tp2_pct *= TREND_ADJUSTMENT
            sl_pct *= TREND_ADJUSTMENT
            log(f"Применена корректировка для трендового рынка: TP2={tp2_pct:.4f}, SL={sl_pct:.4f}", level="DEBUG")

    # Корректировки на основе оценки для слабых сигналов
    if score <= 3:
        tp1_pct *= 0.8
        tp2_pct = None  # Отключаем TP2 для слабых сигналов
        sl_pct *= 0.8
        log(f"Применена корректировка для слабого сигнала: TP1={tp1_pct:.4f}, TP2=None, SL={sl_pct:.4f}", level="DEBUG")

    # Расчет конечных цен - с дополнительной проверкой
    try:
        if side.lower() == "buy":
            tp1_price = entry_price * (1 + tp1_pct)
            tp2_price = entry_price * (1 + tp2_pct) if tp2_pct is not None else None
            sl_price = entry_price * (1 - sl_pct)
        else:  # side == "sell"
            tp1_price = entry_price * (1 - tp1_pct)
            tp2_price = entry_price * (1 - tp2_pct) if tp2_pct is not None else None
            sl_price = entry_price * (1 + sl_pct)

        qty_tp1 = TP1_SHARE
        qty_tp2 = TP2_SHARE if tp2_price is not None else 0

        return (
            round(tp1_price, 4),
            round(tp2_price, 4) if tp2_price is not None else None,
            round(sl_price, 4),
            qty_tp1,
            qty_tp2,
        )
    except Exception as e:
        log(f"Ошибка при расчете конечных цен TP/SL: {e}", level="ERROR")
        # Возвращаем безопасные дефолтные значения при ошибке
        return None, None, None, TP1_SHARE, 0
