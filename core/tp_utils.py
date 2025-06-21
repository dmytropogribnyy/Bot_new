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

    direction = direction.upper()  # ✅ normalize once here

    tp1_pct = tp1_pct or TP1_PERCENT
    tp2_pct = tp2_pct or TP2_PERCENT
    sl_pct = sl_pct or SL_PERCENT

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
    from utils_core import get_runtime_config
    from utils_logging import log

    if min_profit_usd is None:
        # ✅ получаем порог из runtime config
        config = get_runtime_config()
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
    Использует округление по step_size. Если TP не выставлены — SL не ставится.
    Логирует каждую попытку в tp_sl_debug.csv через log_tp_sl_event.
    """
    from core.binance_api import convert_symbol, round_step_size
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

    try:
        cfg = get_runtime_config()
        min_total_qty = cfg.get("min_total_qty_for_tp_full", 0.0035)

        api_symbol = convert_symbol(symbol)
        market_info = exchange.markets.get(api_symbol, {})
        if not market_info:
            log(f"[TP/SL] {symbol}: No market info found — aborting TP/SL", level="ERROR")
            return False

        min_qty = market_info.get("limits", {}).get("amount", {}).get("min", 0.001)

        if qty < min_total_qty:
            log(f"[TP-Fallback] {symbol}: qty {qty:.4f} < {min_total_qty}, fallback to TP1-only logic", level="WARNING")
            send_telegram_message(f"⚠️ {symbol}: qty too low for full TP setup. Routing all to TP1.")
            tp_price = tp_prices[0]
            tp_qty = round_step_size(symbol, qty)

            if tp_qty >= min_qty:
                order = safe_call_retry(
                    lambda: exchange.create_limit_sell_order(api_symbol, tp_qty, tp_price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, tp_qty, tp_price),
                    label=f"tp1_fallback_{symbol}",
                )
                if order:
                    trade_manager.update_trade(symbol, "tp1_price", tp_price)
                    trade_manager.update_trade(symbol, "tp1_qty", tp_qty)
                    log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "success", reason="fallback_only_tp1")
                    log(f"[TP-Fallback] {symbol}: Executed TP1-only fallback with qty={tp_qty}, price={tp_price}", level="INFO")
                else:
                    log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "failure", reason="order_rejected")
                    return False
            else:
                log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "skipped", reason="qty_too_small")
                return False

            # SL
            skip_sl = False
            min_gap = entry_price * 0.001
            if (side == "buy" and sl_price >= entry_price - min_gap) or (side == "sell" and sl_price <= entry_price + min_gap):
                log(f"[SL-Skip] {symbol}: SL too close to entry → skipped", level="WARNING")
                send_telegram_message(f"⚠️ {symbol}: SL skipped — too close to entry")
                log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="too_close")
                skip_sl = True

            if not skip_sl:
                sl_order = safe_call_retry(
                    lambda: exchange.create_order(
                        api_symbol,
                        type="STOP_MARKET",
                        side="sell" if side == "buy" else "buy",
                        amount=qty,
                        params={"stopPrice": sl_price, "reduceOnly": True},
                    ),
                    label=f"sl_stop_market_{symbol}",
                )
                if sl_order:
                    trade_manager.update_trade(symbol, "sl_price", sl_price)
                    log_tp_sl_event(symbol, "SL", qty, sl_price, "success", reason="fallback_mode")
                else:
                    log_tp_sl_event(symbol, "SL", qty, sl_price, "failure", reason="order_rejected")
                    return False

            trade_manager.update_trade(symbol, "tp_sl_success", True)
            return True

        # === Обычная логика ===
        shares = ["tp1", "tp2", "tp3"]
        usable_levels = []
        tp_adjusted = [0.0, 0.0, 0.0]
        orders = []
        tp_total_placed = 0
        failed_levels = []

        trade_data = trade_manager.get_trade(symbol) or {}
        for i in range(3):
            share_key = f"{shares[i]}_share"
            raw_share = trade_data.get(share_key, 0.0)
            try:
                share = float(raw_share)
            except Exception:
                share = 0.0

            raw_qty = qty * share
            qty_i = round_step_size(symbol, raw_qty)

            if not isinstance(qty_i, float) or qty_i <= 0:
                continue

            tp_adjusted[i] = qty_i
            if qty_i >= min_qty:
                usable_levels.append(i)

        fallback_qty = sum(tp_adjusted[i] for i in [1, 2] if i not in usable_levels)
        if fallback_qty > 0:
            log(f"[TP-Fallback] {symbol}: redirecting {fallback_qty:.4f} from TP2/3 to TP1", level="DEBUG")
            tp_adjusted[0] = round_step_size(symbol, tp_adjusted[0] + fallback_qty)

        for i in range(3):
            level = shares[i]
            qty_i = tp_adjusted[i]
            price = tp_prices[i]
            if qty_i < min_qty:
                failed_levels.append(level.upper())
                log_tp_sl_event(symbol, level.upper(), qty_i, price, "skipped", reason="qty_too_small")
                continue

            order = safe_call_retry(
                lambda: exchange.create_limit_sell_order(api_symbol, qty_i, price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, qty_i, price),
                label=f"tp_limit_{symbol}_{i}",
            )

            if order:
                orders.append(order)
                tp_total_placed += qty_i
                trade_manager.update_trade(symbol, f"{level}_price", price)
                trade_manager.update_trade(symbol, f"{level}_qty", qty_i)
                log_tp_sl_event(symbol, level.upper(), qty_i, price, "success")
            else:
                failed_levels.append(level.upper())
                log_tp_sl_event(symbol, level.upper(), qty_i, price, "failure", reason="order_rejected")

        if tp_total_placed == 0:
            log(f"[TP/SL] {symbol}: ❌ No TP orders were placed — skipping SL", level="ERROR")
            send_telegram_message(f"❌ {symbol}: No TP levels could be placed — SL not set")
            log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="no_tp")
            trade_manager.update_trade(symbol, "tp_sl_success", False)
            return False

        min_gap = entry_price * 0.001
        skip_sl = False
        if (side == "buy" and sl_price >= entry_price - min_gap) or (side == "sell" and sl_price <= entry_price + min_gap):
            log(f"[SL-Skip] {symbol}: SL too close to entry → skipped", level="WARNING")
            send_telegram_message(f"⚠️ {symbol}: SL skipped — too close to entry")
            log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="too_close")
            skip_sl = True

        if not skip_sl:
            sl_order = safe_call_retry(
                lambda: exchange.create_order(
                    api_symbol,
                    type="STOP_MARKET",
                    side="sell" if side == "buy" else "buy",
                    amount=qty,
                    params={"stopPrice": sl_price, "reduceOnly": True},
                ),
                label=f"sl_stop_market_{symbol}",
            )
            if sl_order:
                trade_manager.update_trade(symbol, "sl_price", sl_price)
                log_tp_sl_event(symbol, "SL", qty, sl_price, "success")
            else:
                log_tp_sl_event(symbol, "SL", qty, sl_price, "failure", reason="order_rejected")
                return False

        trade_manager.update_trade(symbol, "tp_sl_success", True)
        return True

    except Exception as e:
        log(f"[TP/SL ERROR] {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ {symbol} TP/SL error: {e}")
        return False
