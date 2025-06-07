# tp_utils.py

import os

import pandas as pd

from common.config_loader import (
    AUTO_TP_SL_ENABLED,
    FLAT_ADJUSTMENT,
    SL_PERCENT,
    TP1_PERCENT,
    TP1_SHARE,
    TREND_ADJUSTMENT,
)
from utils_logging import log


def calculate_tp_levels(entry_price: float, side: str, df=None, regime: str = None):
    """
    Финальный вариант для "TP1 + SL + (trailing вместо TP2)":

      - TP1 = ATR * 1.0
      - TP2 = None (убираем жёсткий потолок)
      - SL  = ATR * 1.5

    Если ATR недоступен, fallback на TP1_PERCENT, SL_PERCENT.
    """

    if entry_price is None or entry_price <= 0:
        log(f"[calculate_tp_levels] Некорректная цена входа {entry_price}", level="ERROR")
        return None, None, None, TP1_SHARE, 0

    if not side or side.lower() not in ("buy", "sell"):
        log(f"[calculate_tp_levels] Некорректное значение side={side}", level="ERROR")
        return None, None, None, TP1_SHARE, 0

    # Дефолты (fallback)
    tp1_pct = TP1_PERCENT
    sl_pct = SL_PERCENT

    if df is not None and "atr" in df.columns and not df["atr"].empty:
        try:
            atr = df["atr"].iloc[-1]
            if atr and atr > 0:
                atr_pct = atr / entry_price
                # TP1 = ATR × 1.0
                # SL  = ATR × 1.5
                tp1_pct = max(atr_pct * 1.0, TP1_PERCENT)
                sl_pct = max(atr_pct * 1.5, SL_PERCENT)

                log(
                    f"[calculate_tp_levels] ATR-based: ATR={atr:.6f}, TP1={tp1_pct:.4f}, SL={sl_pct:.4f}",
                    level="DEBUG",
                )
            else:
                log("[calculate_tp_levels] Невалидный ATR, используем fallback", level="WARNING")
        except Exception as e:
            log(f"[calculate_tp_levels] Ошибка расчёта ATR: {e}", level="ERROR")

    # Если у вас есть regime (flat/trend) — можно чуть корректировать tp1_pct / sl_pct
    if AUTO_TP_SL_ENABLED and regime:
        if regime == "flat":
            tp1_pct *= FLAT_ADJUSTMENT
            sl_pct *= FLAT_ADJUSTMENT
        elif regime == "trend":
            sl_pct *= TREND_ADJUSTMENT

    # Подсчитаем финальные цены
    side_lower = side.lower()
    try:
        if side_lower == "buy":
            tp1_price = entry_price * (1 + tp1_pct)
            # tp2 = None
            tp2_price = None
            sl_price = entry_price * (1 - sl_pct)
        else:
            tp1_price = entry_price * (1 - tp1_pct)
            tp2_price = None
            sl_price = entry_price * (1 + sl_pct)

        # TP1 приоритет
        qty_tp1 = TP1_SHARE
        qty_tp2 = 0  # нет TP2

        return (
            round(tp1_price, 4),
            tp2_price,
            round(sl_price, 4),
            qty_tp1,
            qty_tp2,
        )
    except Exception as e:
        log(f"[calculate_tp_levels] Ошибка при расчёте: {e}", level="ERROR")
        return None, None, None, TP1_SHARE, 0


def log_trade_result(symbol, side, entry_price, exit_price, quantity, pnl, duration, reason=None):
    """
    Proxy-обёртка для логирования результатов сделки (через tp_logger).
    """
    from tp_logger import log_trade_result as logger_log_trade_result

    # Маппим параметры под tp_logger
    return logger_log_trade_result(
        symbol=symbol,
        direction=side,
        entry_price=entry_price,
        exit_price=exit_price,
        qty=quantity,
        tp1_hit=False,
        tp2_hit=False,
        sl_hit=(reason == "sl" if reason else False),
        pnl_percent=pnl,
        duration_minutes=duration,
        htf_confirmed=False,
        atr=0.0,
        adx=0.0,
        bb_width=0.0,
        result_type=reason or "manual",
    )


def adjust_microprofit_exit(current_pnl_percent, balance=None, duration_minutes=None, position_percentage=None):
    """
    Решение о micro-profit выходе.

    Args:
        current_pnl_percent (float): Текущее значение прибыли в процентах
        balance (float): Текущий баланс счёта
        duration_minutes (int): Сколько минут сделка открыта
        position_percentage (float): Доля позиции от баланса
    """
    if balance is None:
        micro_profit_target = 0.5
    elif balance < 100:
        micro_profit_target = 0.4
    elif balance < 200:
        micro_profit_target = 0.6
    else:
        micro_profit_target = 0.8

    if position_percentage is not None:
        if position_percentage < 0.1:
            micro_profit_target *= 0.7
        elif position_percentage < 0.15:
            micro_profit_target *= 0.8

    if duration_minutes is not None:
        if duration_minutes > 60:
            micro_profit_target *= 0.7
        elif duration_minutes > 30:
            micro_profit_target *= 0.8

    micro_profit_target = max(0.2, micro_profit_target)

    return current_pnl_percent >= micro_profit_target


def get_tp_performance_stats():
    """
    Возвращает статистику винрейта по TP1/TP2 на основе tp_logger.csv.
    """
    try:
        from tp_logger import TP_LOG_FILE

        if not os.path.exists(TP_LOG_FILE):
            return {}

        df = pd.read_csv(TP_LOG_FILE)

        stats = {}
        for symbol in df["Symbol"].unique():
            symbol_data = df[df["Symbol"] == symbol]
            total_trades = len(symbol_data)

            tp_hits = symbol_data[symbol_data["Result"].isin(["TP1", "TP2"])]
            win_count = len(tp_hits)

            tp1_count = len(symbol_data[symbol_data["Result"] == "TP1"])
            tp2_count = len(symbol_data[symbol_data["Result"] == "TP2"])

            winrate = win_count / total_trades if total_trades > 0 else 0
            tp2_opportunities = tp1_count + tp2_count
            tp2_winrate = tp2_count / tp2_opportunities if tp2_opportunities > 0 else 0

            stats[symbol] = {
                "winrate": winrate,
                "tp1_count": tp1_count,
                "tp2_count": tp2_count,
                "tp2_winrate": tp2_winrate,
                "total_trades": total_trades,
            }
        return stats

    except Exception as e:
        from utils_logging import log

        log(f"[TPUtils] Error getting TP performance stats: {e}", level="ERROR")
        return {}
