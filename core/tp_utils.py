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
        tp1_price, tp2_price, sl_price, share_tp1, share_tp2, tp3_share
    """
    import numpy as np

    from common.config_loader import (
        SL_PERCENT,
        TP1_PERCENT,
        TP1_SHARE,
        TP2_PERCENT,
        TP2_SHARE,
    )

    direction = direction.upper()  # ✅ normalize once here

    tp1_pct = TP1_PERCENT if tp1_pct is None else tp1_pct
    tp2_pct = TP2_PERCENT if tp2_pct is None else tp2_pct
    sl_pct = SL_PERCENT if sl_pct is None else sl_pct

    share_tp1 = TP1_SHARE
    share_tp2 = TP2_SHARE

    try:
        if df is not None and "atr" in df.columns and not df["atr"].isna().all():
            atr_value = df["atr"].iloc[-1]
            if np.isnan(atr_value) or atr_value <= 0:
                raise ValueError("Invalid ATR")

            if regime == "flat":
                tp1_pct = atr_value * 1.0 / entry_price
                sl_pct = atr_value * 1.5 / entry_price
            elif regime == "trend":
                tp1_pct = atr_value * 1.7 / entry_price
                sl_pct = atr_value * 1.2 / entry_price
            else:
                tp1_pct = atr_value * 2.0 / entry_price
                sl_pct = atr_value * 1.5 / entry_price

            tp2_pct = tp1_pct * 2
    except Exception as e:
        log(f"[TP] ATR fallback used due to error: {e}", level="WARNING")

    # 🔹 DEBUG лог итоговых процентов
    log(f"[TP_LEVELS] {direction} | tp1_pct={tp1_pct:.4f}, tp2_pct={tp2_pct:.4f}, sl_pct={sl_pct:.4f}", level="DEBUG")

    # 🔹 Проверка суммарной доли
    if share_tp1 + share_tp2 > 1.0:
        log(f"[TP_SHARES] Sum of TP shares exceeds 1.0: {share_tp1 + share_tp2:.2f}", level="ERROR")
        return None, None, None, None, None, None

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
        return None, None, None, None, None, None

    if any(np.isnan(x) or x <= 0 for x in [tp1_price, tp2_price, sl_price]):
        log(f"[TP] Invalid TP/SL values => tp1={tp1_price}, tp2={tp2_price}, sl={sl_price}", level="ERROR")
        return None, None, None, None, None, None

    tp3_share = max(0.0, 1.0 - (share_tp1 + share_tp2))
    log(f"[TP] Calculated tp3_share = {tp3_share:.2f}", level="DEBUG")

    return tp1_price, tp2_price, sl_price, share_tp1, share_tp2, tp3_share


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
    from utils_core import get_runtime_config
    from utils_logging import log

    config = get_runtime_config()
    adaptive_enabled = config.get("adaptive_tp_threshold_enabled", False)

    if adaptive_enabled:
        atr_pct = abs(tp1 - entry) / entry
        entry_notional = qty * entry
        min_profit_usd = max(entry_notional * atr_pct * 0.6, 0.01)  # ≥ $0.01, адаптивно по ATR
        log(f"[ProfitCheck] Adaptive threshold → min_profit={min_profit_usd:.4f}$ (ATR={atr_pct:.4f})", level="DEBUG")
    elif min_profit_usd is None:
        min_profit_usd = config.get("min_profit_threshold", 0.06)
        log(f"[ProfitCheck] Runtime config threshold → min_profit={min_profit_usd:.2f}$", level="DEBUG")
    else:
        log(f"[ProfitCheck] Explicit threshold passed → min_profit={min_profit_usd:.2f}$", level="DEBUG")

    # 🔒 safety нижняя граница
    min_profit_usd = max(min_profit_usd, 0.05)

    gross_profit = abs(tp1 - entry) * qty * share_tp1
    commission = 2 * qty * entry * fee_rate
    net_profit = round(gross_profit - commission, 2)
    is_valid = net_profit >= round(min_profit_usd, 2)

    verdict = "✅ OK" if is_valid else "❌ reject"
    log(f"[ProfitCheck] expected={net_profit:.2f}$ vs required={min_profit_usd:.2f}$ → {verdict}", level="DEBUG")

    return is_valid, round(net_profit, 2)


def place_take_profit_and_stop_loss_orders(symbol, side, entry_price, qty, tp_prices, sl_price):
    """
    Ставит TP1/TP2/TP3 и SL ордера с адаптацией под малые qty.
    Проверяет step_size, min_qty, notional. Если ни один TP не прошёл — SL не ставится.
    Сохраняет tp_total_qty и логирует нераспределённый остаток.
    """
    from core.binance_api import convert_symbol, get_symbol_info, round_step_size
    from core.exchange_init import exchange
    from core.tp_sl_logger import log_tp_sl_event
    from core.trade_engine import trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import get_runtime_config, safe_call_retry
    from utils_logging import log

    if not tp_prices or not isinstance(tp_prices, (list, tuple)) or len(tp_prices) < 3 or sl_price is None:
        msg = f"[TP/SL] Invalid TP/SL params for {symbol}. Skipping TP/SL."
        log(msg, level="ERROR")
        send_telegram_message(f"⚠️ {msg}")
        return False

    cfg = get_runtime_config()
    min_total_qty = cfg.get("min_total_qty_for_tp_full", 0.0035)
    force_sl = cfg.get("FORCE_SL_ALWAYS", False)

    api_symbol = convert_symbol(symbol)
    market_info = get_symbol_info(symbol)

    if not market_info:
        log(f"[TP/SL] {symbol}: No market info found — aborting", level="ERROR")
        return False

    step_size = market_info.get("precision", {}).get("amount", 0.001)
    if not step_size or step_size <= 0:
        log(f"[TP/SL] {symbol}: Invalid step_size={step_size}, fallback=0.001", level="WARNING")
        step_size = 0.001

    min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.001)
    min_notional = market_info.get("limits", {}).get("cost", {}).get("min", 5.0)

    trade_data = trade_manager.get_trade(symbol) or {}

    # === Fallback mode: TP1 only
    if qty < min_total_qty:
        log(f"[TP-Fallback] {symbol}: qty={qty:.6f} < {min_total_qty}, using TP1-only mode", level="WARNING")
        send_telegram_message(f"⚠️ {symbol}: fallback → TP1 only, qty={qty:.4f}")

        tp_price = tp_prices[0]
        tp_qty = round_step_size(symbol, qty)
        notional = tp_qty * tp_price

        if tp_qty < min_qty or notional < min_notional:
            log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "skipped", reason="qty_too_small_or_notional")
            return False

        try:
            order = safe_call_retry(
                lambda: exchange.create_limit_sell_order(api_symbol, tp_qty, tp_price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, tp_qty, tp_price),
                label=f"tp1_fallback_{symbol}",
            )
            if order:
                trade_manager.update_trade(symbol, "tp1_price", tp_price)
                trade_manager.update_trade(symbol, "tp1_qty", tp_qty)
                trade_manager.update_trade(symbol, "tp_fallback_used", True)
                trade_manager.update_trade(symbol, "tp_total_qty", tp_qty)
                log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "success", reason="fallback")
            else:
                log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "failure", reason="order_rejected")
                return False
        except Exception as e:
            log(f"[TP-Fallback] {symbol} error: {e}", level="ERROR")
            return False

        # === SL
        if sl_price:
            try:
                sl_order = safe_call_retry(
                    lambda: exchange.create_order(
                        api_symbol,
                        type="STOP_MARKET",
                        side="sell" if side == "buy" else "buy",
                        amount=qty,
                        params={"stopPrice": sl_price, "reduceOnly": True},
                    ),
                    label=f"sl_fallback_{symbol}",
                )
                if sl_order:
                    trade_manager.update_trade(symbol, "sl_price", sl_price)
                    log_tp_sl_event(symbol, "SL", qty, sl_price, "success", reason="fallback_mode")
            except Exception as e:
                log(f"[SL] Fallback SL error for {symbol}: {e}", level="ERROR")
                return False

        trade_manager.update_trade(symbol, "tp_sl_success", True)
        return True

    # === Обычная логика (TP1/TP2/TP3)
    tp_total = 0.0
    success_count = 0
    for i, price in enumerate(tp_prices):
        level = f"TP{i+1}"
        share = trade_data.get(f"tp{i+1}_share", 0.0)
        raw_qty = qty * share
        qty_i = round_step_size(symbol, raw_qty)
        notional = qty_i * price

        log(f"[TP-TRY] {symbol} {level} → raw={raw_qty:.6f}, rounded={qty_i:.6f}, notional={notional:.2f}", level="DEBUG")

        if qty_i < min_qty or notional < min_notional:
            log_tp_sl_event(symbol, level, qty_i, price, "skipped", reason="qty_too_small_or_notional")
            continue

        try:
            order = safe_call_retry(
                lambda: exchange.create_limit_sell_order(api_symbol, qty_i, price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, qty_i, price),
                label=f"tp_limit_{symbol}_{i}",
            )
            if order:
                trade_manager.update_trade(symbol, f"tp{i+1}_price", price)
                trade_manager.update_trade(symbol, f"tp{i+1}_qty", qty_i)
                log_tp_sl_event(symbol, level, qty_i, price, "success")
                success_count += 1
                tp_total += qty_i
            else:
                log_tp_sl_event(symbol, level, qty_i, price, "failure", reason="order_rejected")
        except Exception as e:
            log(f"[TP] {symbol} {level} order error: {e}", level="ERROR")
            log_tp_sl_event(symbol, level, qty_i, price, "failure", reason="exception")

    trade_manager.update_trade(symbol, "tp_total_qty", tp_total)
    trade_manager.update_trade(symbol, "tp_fallback_used", False)

    # ➕ Лог, если есть остаток
    remainder = qty - tp_total
    if remainder >= min_qty and remainder * tp_prices[0] >= min_notional:
        log(f"[TP] {symbol}: Unallocated qty={remainder:.6f} remaining after TP placement", level="DEBUG")
        send_telegram_message(f"ℹ️ {symbol}: {remainder:.4f} qty not allocated to TP — consider fallback TP3 or soft exit.")

    if success_count == 0:
        log(f"[TP/SL] {symbol}: ❌ No TP levels placed — SL skipped", level="ERROR")
        send_telegram_message(f"❌ {symbol}: No TP orders placed — SL skipped")
        log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="no_tp")
        trade_manager.update_trade(symbol, "tp_sl_success", False)
        return False

    # === SL
    skip_sl = False
    min_gap = entry_price * 0.001
    if (side == "buy" and sl_price >= entry_price - min_gap) or (side == "sell" and sl_price <= entry_price + min_gap):
        log(f"[SL] {symbol}: SL too close to entry — skipped", level="WARNING")
        log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="too_close")
        skip_sl = True

    if not skip_sl or force_sl:
        try:
            sl_order = safe_call_retry(
                lambda: exchange.create_order(
                    api_symbol,
                    type="STOP_MARKET",
                    side="sell" if side == "buy" else "buy",
                    amount=qty,
                    params={"stopPrice": sl_price, "reduceOnly": True},
                ),
                label=f"sl_stop_{symbol}",
            )
            if sl_order:
                trade_manager.update_trade(symbol, "sl_price", sl_price)
                log_tp_sl_event(symbol, "SL", qty, sl_price, "success")
        except Exception as e:
            log(f"[SL] Order error for {symbol}: {e}", level="ERROR")
            log_tp_sl_event(symbol, "SL", qty, sl_price, "failure", reason="exception")
            return False

    trade_manager.update_trade(symbol, "tp_sl_success", True)
    return True
