# tp_utils.py

import os

import pandas as pd

from utils_logging import log


def calculate_tp_levels(entry_price, direction, df=None, regime="neutral", tp1_pct=None, tp2_pct=None, sl_pct=None):
    """
    Рассчитывает TP1, TP2, SL уровни и их доли.
    Учитывает:
      - ATR (если доступен),
      - режим рынка (flat/trend),
      - direction (BUY/SELL),
      - фиксированные проценты или значения из df.

    Возвращает:
        tp1_price, tp2_price, sl_price, share_tp1, share_tp2
    """
    import numpy as np

    from common.config_loader import (
        SL_PERCENT,
        TP1_PERCENT,
        TP1_SHARE,
        TP2_PERCENT,
        TP2_SHARE,
    )

    # === Fallback значения
    tp1_pct = tp1_pct or TP1_PERCENT
    tp2_pct = tp2_pct or TP2_PERCENT
    sl_pct = sl_pct or SL_PERCENT

    share_tp1 = TP1_SHARE
    share_tp2 = TP2_SHARE

    # === Попытка адаптации через ATR
    try:
        if df is not None and "atr" in df.columns and not df["atr"].isna().all():
            atr_value = df["atr"].iloc[-1]
            if np.isnan(atr_value) or atr_value <= 0:
                raise ValueError("Invalid ATR")

            # Flat рынок → TP ниже, SL шире
            if regime == "flat":
                tp1_pct = atr_value * 1.0 / entry_price
                sl_pct = atr_value * 1.5 / entry_price

            # Trend рынок → TP шире, SL уже
            elif regime == "trend":
                tp1_pct = atr_value * 1.7 / entry_price
                sl_pct = atr_value * 1.2 / entry_price

            # Breakout или neutral → более агрессивные TP
            else:
                tp1_pct = atr_value * 2.0 / entry_price
                sl_pct = atr_value * 1.5 / entry_price

            tp2_pct = tp1_pct * 2
    except Exception as e:
        log(f"[TP] ATR fallback used due to error: {e}", level="WARNING")
        # Используем фиксированные значения

    # === Направление: BUY / SELL
    if direction == "BUY":
        tp1_price = entry_price * (1 + tp1_pct)
        tp2_price = entry_price * (1 + tp2_pct)
        sl_price = entry_price * (1 - sl_pct)
    elif direction == "SELL":
        tp1_price = entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 - tp2_pct)
        sl_price = entry_price * (1 + sl_pct)
    else:
        log(f"[TP] Invalid direction: {direction}", level="ERROR")
        return None, None, None, None, None

    # === Проверка на валидность
    if any(np.isnan(x) or x <= 0 for x in [tp1_price, tp2_price, sl_price]):
        log(f"[TP] Invalid TP/SL values => tp1={tp1_price}, tp2={tp2_price}, sl={sl_price}", level="ERROR")
        return None, None, None, None, None

    return tp1_price, tp2_price, sl_price, share_tp1, share_tp2


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
    Возвращает статистику TP1/TP2 по tp_logger.csv:
    - общее число сделок,
    - TP1 / TP2 хиты,
    - winrate,
    - TP2 winrate среди всех TP.
    """
    from tp_logger import TP_LOG_FILE
    from utils_logging import log

    stats = {}

    try:
        if not os.path.exists(TP_LOG_FILE):
            log(f"[TPUtils] TP log file not found: {TP_LOG_FILE}", level="WARNING")
            return {}

        df = pd.read_csv(TP_LOG_FILE)

        required_cols = {"Symbol", "Result"}
        if not required_cols.issubset(df.columns):
            log(f"[TPUtils] CSV missing columns: {required_cols - set(df.columns)}", level="ERROR")
            return {}

        grouped = df.groupby("Symbol")

        for symbol, group in grouped:
            total = len(group)
            if total == 0:
                continue

            tp1_count = (group["Result"] == "TP1").sum()
            tp2_count = (group["Result"] == "TP2").sum()
            win_count = tp1_count + tp2_count

            tp2_opportunities = tp1_count + tp2_count
            tp2_winrate = tp2_count / tp2_opportunities if tp2_opportunities else 0
            winrate = win_count / total

            stats[symbol] = {
                "total_trades": total,
                "tp1_count": tp1_count,
                "tp2_count": tp2_count,
                "winrate": round(winrate, 4),
                "tp2_winrate": round(tp2_winrate, 4),
            }

        return stats

    except Exception as e:
        log(f"[TPUtils] Error getting TP performance stats: {e}", level="ERROR")
        return {}


def check_min_profit(entry, tp1, qty, share_tp1, direction, fee_rate, min_profit_usd=None):
    """
    Проверяет, даст ли TP1 достаточно чистой прибыли.
    Возвращает (bool: хватает ли, float: ожидаемая чистая прибыль)
    """
    from utils_core import get_cached_balance
    from utils_logging import log

    # 🧠 Адаптивный порог в зависимости от баланса
    if min_profit_usd is None:
        balance = get_cached_balance()
        if balance <= 300:
            min_profit_usd = 0.06
        elif balance <= 500:
            min_profit_usd = 0.08
        else:
            min_profit_usd = 0.10

        log(f"[ProfitCheck] Adaptive threshold → balance={balance:.2f} → min_profit={min_profit_usd:.2f}$", level="DEBUG")

    gross_profit = abs(tp1 - entry) * qty * share_tp1
    commission = 2 * qty * entry * fee_rate  # вход + выход
    net_profit = gross_profit - commission

    log(f"[ProfitCheck] expected={net_profit:.2f}$ vs required={min_profit_usd:.2f}$ → {'✅ OK' if net_profit >= min_profit_usd else '❌ reject'}", level="DEBUG")

    return net_profit >= min_profit_usd, round(net_profit, 2)


def place_take_profit_and_stop_loss_orders(api_symbol, side, qty, entry_price, tp1_pct=0.01, sl_pct=0.01):
    """
    Устанавливает TP1, TP2 и SL ордера после входа:
    - TP1 на 80% позиции
    - TP2 на 20% позиции
    - SL на 100% позиции (STOP_MARKET через create_order)
    """
    from core.exchange_init import exchange
    from utils_logging import log

    try:
        open_orders = exchange.fetch_open_orders(api_symbol)
        reduce_orders = [o for o in open_orders if o.get("reduceOnly")]
        if reduce_orders:
            log(f"[TP/SL] {api_symbol}: reduceOnly orders already exist ({len(reduce_orders)}) — skipping setup", level="WARNING")
            return

        tp1_price = entry_price * (1 + tp1_pct) if side.lower() == "buy" else entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 + 2 * tp1_pct) if side.lower() == "buy" else entry_price * (1 - 2 * tp1_pct)
        sl_price = entry_price * (1 - sl_pct) if side.lower() == "buy" else entry_price * (1 + sl_pct)

        tp1_price = round(tp1_price, 6)
        tp2_price = round(tp2_price, 6)
        sl_price = round(sl_price, 6)
        side_close = "sell" if side.lower() == "buy" else "buy"

        tp1_qty = round(qty * 0.8, 6)
        tp2_qty = round(qty * 0.2, 6)

        # TP1
        try:
            exchange.create_limit_order(
                api_symbol,
                side_close,
                tp1_qty,
                tp1_price,
                {"reduceOnly": True, "postOnly": True, "timeInForce": "GTC"},
            )
            log(f"[TP] {api_symbol}: TP1 placed at {tp1_price:.6f} for {tp1_qty}", level="INFO")
        except Exception as e:
            log(f"[TP] Failed to place TP1 for {api_symbol}: {e}", level="ERROR")

        # TP2
        try:
            exchange.create_limit_order(
                api_symbol,
                side_close,
                tp2_qty,
                tp2_price,
                {"reduceOnly": True, "postOnly": True, "timeInForce": "GTC"},
            )
            log(f"[TP] {api_symbol}: TP2 placed at {tp2_price:.6f} for {tp2_qty}", level="INFO")
        except Exception as e:
            log(f"[TP] Failed to place TP2 for {api_symbol}: {e}", level="ERROR")

        # SL
        try:
            exchange.create_order(
                symbol=api_symbol,
                type="STOP_MARKET",
                side=side_close,
                amount=qty,
                params={
                    "stopPrice": sl_price,
                    "reduceOnly": True,
                },
            )
            log(f"[SL] {api_symbol}: SL placed at {sl_price:.6f} for {qty}", level="INFO")
        except Exception as e:
            log(f"[SL] Failed to place SL for {api_symbol}: {e}", level="ERROR")

    except Exception as e:
        log(f"[TP/SL] General error placing TP/TP2/SL for {api_symbol}: {e}", level="ERROR")
        raise
