# tp_utils.py

import os

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


def log_trade_result(symbol, side, entry_price, exit_price, quantity, pnl, duration, reason=None, account_category=None):
    """
    Bridge function that properly forwards all parameters to the actual log implementation.
    """
    from tp_logger import log_trade_result as logger_log_trade_result

    # Handle conversion of parameters to match tp_logger.py's implementation
    return logger_log_trade_result(
        symbol=symbol,
        direction=side,
        entry_price=entry_price,
        exit_price=exit_price,
        qty=quantity,
        tp1_hit=False,  # Default value, adjust as needed
        tp2_hit=False,  # Default value, adjust as needed
        sl_hit=(reason == "sl" if reason else False),
        pnl_percent=pnl,
        duration_minutes=duration,
        htf_confirmed=False,  # Default value
        atr=0.0,  # Default value
        adx=0.0,  # Default value
        bb_width=0.0,  # Default value
        result_type=reason or "manual",
    )


def adjust_microprofit_exit(current_pnl_percent, balance=None, duration_minutes=None, position_percentage=None):
    """
    Determine if a position should be closed with a small profit.
    Enhanced with position size and duration factors.

    Args:
        current_pnl_percent: Current profit percentage
        balance: Current account balance
        duration_minutes: How long the position has been open
        position_percentage: Position size as percentage of account

    Returns:
        bool: True if position should be closed, False otherwise
    """
    # Базовый порог по размеру счета
    if balance is None:
        micro_profit_target = 0.5  # Дефолтное значение
    elif balance < 100:
        micro_profit_target = 0.4  # Более низкий порог для маленьких счетов
    elif balance < 200:
        micro_profit_target = 0.6  # Средний порог
    else:
        micro_profit_target = 0.8  # Более высокий порог для больших счетов

    # Корректировка по размеру позиции
    if position_percentage is not None:
        if position_percentage < 0.1:  # Очень маленькая позиция
            micro_profit_target *= 0.7  # На 30% ниже порог
        elif position_percentage < 0.15:  # Маленькая позиция
            micro_profit_target *= 0.8  # На 20% ниже порог

    # Корректировка по времени удержания
    if duration_minutes is not None:
        if duration_minutes > 60:  # Более часа
            micro_profit_target *= 0.7  # На 30% ниже порог
        elif duration_minutes > 30:  # Более 30 минут
            micro_profit_target *= 0.8  # На 20% ниже порог

    # Убедиться, что порог не слишком низкий
    micro_profit_target = max(0.2, micro_profit_target)

    return current_pnl_percent >= micro_profit_target


def get_tp_performance_stats():
    """
    Get performance statistics for trading pairs based on TP history.

    Returns:
        dict: Dictionary mapping symbols to their performance statistics
            {
                "BTC/USDC": {
                    "winrate": 0.75,
                    "tp1_count": 10,
                    "tp2_count": 5,
                    "tp2_winrate": 0.6,
                    "total_trades": 20
                },
                ...
            }
    """
    try:
        import pandas as pd

        from tp_logger import TP_LOG_FILE

        # Check if the file exists
        if not os.path.exists(TP_LOG_FILE):
            return {}

        # Load the TP performance data
        df = pd.read_csv(TP_LOG_FILE)

        # Group by symbol and calculate statistics
        stats = {}
        for symbol in df["Symbol"].unique():
            symbol_data = df[df["Symbol"] == symbol]

            # Total trades
            total_trades = len(symbol_data)

            # Win count (TP1 or TP2)
            tp_hits = symbol_data[symbol_data["Result"].isin(["TP1", "TP2"])]
            win_count = len(tp_hits)

            # TP1 and TP2 counts
            tp1_count = len(symbol_data[symbol_data["Result"] == "TP1"])
            tp2_count = len(symbol_data[symbol_data["Result"] == "TP2"])

            # Calculate winrates
            winrate = win_count / total_trades if total_trades > 0 else 0
            tp2_opportunities = tp1_count + tp2_count  # TP2 can only be hit after TP1
            tp2_winrate = tp2_count / tp2_opportunities if tp2_opportunities > 0 else 0

            stats[symbol] = {"winrate": winrate, "tp1_count": tp1_count, "tp2_count": tp2_count, "tp2_winrate": tp2_winrate, "total_trades": total_trades}

        return stats
    except Exception as e:
        from utils_logging import log

        log(f"[TPUtils] Error getting TP performance stats: {e}", level="ERROR")
        return {}
