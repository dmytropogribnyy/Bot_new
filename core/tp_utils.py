# tp_utils.py

import os

import pandas as pd

from core.exchange_init import exchange
from utils_core import get_runtime_config
from utils_logging import log


def calculate_tp_levels(entry_price, direction, df=None, regime="neutral", tp1_pct=None, tp2_pct=None, sl_pct=None):
    import numpy as np

    from common.config_loader import (
        SL_PERCENT,
        TP1_PERCENT,
        TP1_SHARE,
        TP2_PERCENT,
        TP2_SHARE,
    )
    from utils_logging import log

    direction = direction.upper()
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

    sl_buffer = sl_pct * 0.1  # Можно сделать dynamic: sl_buffer = max(0.001, atr_value * 0.05 / entry_price) if atr_value else sl_pct * 0.1

    if direction == "BUY":
        tp1_price = entry_price * (1 + tp1_pct)
        tp2_price = entry_price * (1 + tp2_pct)
        sl_price = entry_price * (1 - sl_pct - sl_buffer)
    elif direction == "SELL":
        tp1_price = entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 - tp2_pct)
        sl_price = entry_price * (1 + sl_pct + sl_buffer)
    else:
        return None, None, None, None, None, None

    tp3_share = max(0.0, 1.0 - (share_tp1 + share_tp2))
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


def safe_round_and_validate(symbol: str, raw_qty: float) -> float | None:
    """
    Округляет и валидирует qty. Возвращает None, если raw < min_qty или после округления < min_qty/0.
    """
    from core.binance_api import round_step_size
    from core.exchange_init import exchange  # Для доступа к market limits
    from utils_logging import log

    market = exchange.markets.get(symbol)
    min_qty = market["limits"]["amount"]["min"] if market else 0.001  # Fallback

    if raw_qty < min_qty:
        log(f"[safe_qty] Raw qty={raw_qty:.6f} < min_qty={min_qty} for {symbol} — skipping", level="DEBUG")
        return None

    rounded_qty = round_step_size(symbol, raw_qty)
    if rounded_qty <= 0:
        log(f"[safe_qty] Rounded qty={rounded_qty} <= 0 for {symbol} (raw={raw_qty})", level="WARNING")
        return None

    return validate_qty(symbol, rounded_qty)


def place_take_profit_and_stop_loss_orders(symbol, side, entry_price, qty, tp_prices, sl_price):
    """
    Сначала SL, затем TP — для защиты от delay-фейлов.
    tp_sl_success = True только если SL успешен и TP > 0.
    """
    import time

    from core.binance_api import convert_symbol, get_symbol_info
    from core.exchange_init import exchange
    from core.tp_sl_logger import log_tp_sl_event
    from core.tp_utils import safe_round_and_validate
    from core.trade_engine import close_real_trade, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import get_runtime_config, safe_call_retry
    from utils_logging import log

    if not tp_prices or len(tp_prices) < 3 or sl_price is None:
        msg = f"[TP/SL] Invalid params for {symbol} — skipping."
        log(msg, level="ERROR")
        send_telegram_message(f"⚠️ {msg}")
        return False

    cfg = get_runtime_config()
    min_total_qty = cfg.get("min_total_qty_for_tp_full", 0.0035)
    force_sl = cfg.get("FORCE_SL_ALWAYS", False)
    sl_retry_limit = cfg.get("sl_retry_limit", 3)

    api_symbol = convert_symbol(symbol)
    market_info = get_symbol_info(symbol)
    if not market_info:
        log(f"[TP/SL] No market info for {symbol}", level="ERROR")
        return False

    min_qty = market_info["limits"]["amount"]["min"]

    trade_data = trade_manager.get_trade(symbol) or {}
    success_sl = False
    success_tp = 0
    tp_total = 0.0

    # === Pre-check SL vs current price ===
    try:
        ticker = safe_call_retry(exchange.fetch_ticker, api_symbol)
        current_price = ticker["last"] if ticker else entry_price
    except Exception as e:
        log(f"[PreCheck] Failed to fetch ticker for {symbol}: {e} — using entry_price", level="WARNING")
        current_price = entry_price

    if (side == "buy" and sl_price >= current_price) or (side == "sell" and sl_price <= current_price):
        log(f"[SL] {symbol}: would trigger (current={current_price:.4f}, SL={sl_price:.4f}) — closing", level="WARNING")
        log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="would_trigger_now")
        close_real_trade(symbol)
        return False

    # === SL first ===
    min_gap = entry_price * 0.001
    if (side == "buy" and sl_price >= entry_price - min_gap) or (side == "sell" and sl_price <= entry_price + min_gap):
        log(f"[SL] {symbol}: too close to entry — skipped", level="WARNING")
        log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="too_close")
    else:
        try:
            sl_order = safe_call_retry(
                lambda: exchange.create_order(
                    api_symbol,
                    type="STOP_MARKET",
                    side="sell" if side == "buy" else "buy",
                    amount=qty,
                    params={"stopPrice": sl_price, "reduceOnly": True},
                ),
                label=f"sl_{symbol}",
            )
            if sl_order:
                trade_manager.update_trade(symbol, "sl_price", sl_price)
                log_tp_sl_event(symbol, "SL", qty, sl_price, "success")
                log(f"[SL] Success: ID={sl_order.get('id', 'n/a')}", level="DEBUG")
                success_sl = True
        except Exception as e:
            log(f"[SL] Error for {symbol}: {e}", level="ERROR")
            if "trigger" in str(e).lower():
                send_telegram_message(f"❌ {symbol}: SL rejected (would trigger) → closing position")
                log_tp_sl_event(symbol, "SL", qty, sl_price, "skipped", reason="would_trigger")
                close_real_trade(symbol)
                return False
            elif force_sl:
                for retry in range(sl_retry_limit):
                    try:
                        _widen = 1 + (retry + 1) * 0.002
                        widened_sl = sl_price * (1 - 0.002 * (retry + 1)) if side == "buy" else sl_price * (1 + 0.002 * (retry + 1))
                        log(f"[Retry {retry+1}] Widened SL to {widened_sl:.6f}", level="INFO")
                        sl_order = safe_call_retry(
                            lambda: exchange.create_order(
                                api_symbol,
                                type="STOP_MARKET",
                                side="sell" if side == "buy" else "buy",
                                amount=qty,
                                params={"stopPrice": widened_sl, "reduceOnly": True},
                            ),
                            label=f"sl_retry_{symbol}_{retry}",
                        )
                        if sl_order:
                            trade_manager.update_trade(symbol, "sl_price", widened_sl)
                            log_tp_sl_event(symbol, "SL", qty, widened_sl, "success", reason="force_retry")
                            success_sl = True
                            break
                    except Exception:
                        time.sleep(1)
                if not success_sl:
                    send_telegram_message(f"❌ {symbol}: SL retry failed — closing position")
                    close_real_trade(symbol)
                    return False
            else:
                return False

    if not success_sl:
        send_telegram_message(f"❌ {symbol}: SL not placed — skipping TP")
        trade_manager.update_trade(symbol, "tp_sl_success", False)
        return False

    fallback = qty < min_total_qty
    if fallback:
        log(f"[TP-Fallback] {symbol}: qty={qty:.4f} < {min_total_qty}", level="WARNING")
        send_telegram_message(f"⚠️ {symbol}: fallback → TP1 only")
        tp_price = tp_prices[0]
        tp_qty = safe_round_and_validate(symbol, qty)
        if tp_qty:
            try:
                order = safe_call_retry(
                    lambda: exchange.create_limit_sell_order(api_symbol, tp_qty, tp_price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, tp_qty, tp_price),
                    label=f"tp_fallback_{symbol}",
                )
                if order:
                    trade_manager.update_trade(symbol, "tp1_price", tp_price)
                    trade_manager.update_trade(symbol, "tp1_qty", tp_qty)
                    tp_total += tp_qty
                    success_tp += 1
                    log_tp_sl_event(symbol, "TP1", tp_qty, tp_price, "success", reason="fallback")
            except Exception as e:
                log(f"[TP-Fallback] {symbol} error: {e}", level="ERROR")
    else:
        for i, price in enumerate(tp_prices):
            level = f"TP{i+1}"
            share = trade_data.get(f"tp{i+1}_share", 0.0)
            raw_qty = qty * share
            if raw_qty < min_qty:
                log(f"[TP-Skip] {symbol} {level} raw_qty={raw_qty:.6f} < min_qty={min_qty} — skipping", level="DEBUG")
                log_tp_sl_event(symbol, level, raw_qty, price, "skipped", reason="raw_qty_too_small")
                continue
            qty_i = safe_round_and_validate(symbol, raw_qty)
            if not qty_i:
                log_tp_sl_event(symbol, level, raw_qty, price, "skipped", reason="qty_invalid")
                continue
            try:
                order = safe_call_retry(
                    lambda: exchange.create_limit_sell_order(api_symbol, qty_i, price) if side == "buy" else exchange.create_limit_buy_order(api_symbol, qty_i, price),
                    label=f"tp_{symbol}_{i}",
                )
                if order:
                    trade_manager.update_trade(symbol, f"tp{i+1}_price", price)
                    trade_manager.update_trade(symbol, f"tp{i+1}_qty", qty_i)
                    log_tp_sl_event(symbol, level, qty_i, price, "success")
                    tp_total += qty_i
                    success_tp += 1
            except Exception as e:
                log(f"[TP] {symbol} {level} error: {e}", level="ERROR")
                log_tp_sl_event(symbol, level, qty_i, price, "failure", reason="exception")

    trade_manager.update_trade(symbol, "tp_total_qty", tp_total)
    trade_manager.update_trade(symbol, "tp_fallback_used", fallback)

    tp_sl_success = success_sl and tp_total > 0
    trade_manager.update_trade(symbol, "tp_sl_success", tp_sl_success)

    if tp_sl_success:
        send_telegram_message(f"✅ {symbol}: TP/SL orders placed successfully.")
    else:
        send_telegram_message(f"⚠️ {symbol}: TP/SL partially failed (SL ok: {success_sl}, TP hits: {success_tp})")

    return tp_sl_success


def validate_qty(symbol: str, qty: float) -> float | None:
    """
    Проверяет и корректирует qty под правила Binance:
    - min_qty, step_size, precision.
    Возвращает скорректированную qty или None, если недопустима.
    """
    try:
        config = get_runtime_config()
        retry_limit = config.get("market_reload_retry_limit", 3)

        market = exchange.markets.get(symbol)
        if not market:
            for i in range(retry_limit):
                try:
                    log(f"[validate_qty] Market not found for {symbol}, reloading (attempt {i+1})", level="WARNING")
                    exchange.load_markets()
                    market = exchange.markets.get(symbol)
                    if market:
                        break
                except Exception as e:
                    log(f"[validate_qty] Retry {i+1} failed to load markets: {e}", level="ERROR")
            if not market:
                log(f"[validate_qty] Failed to load market info for {symbol}", level="ERROR")
                return None

        min_qty = float(market["limits"]["amount"]["min"])
        precision = int(market["precision"]["amount"])

        step_size = 0.0
        for f in market["info"].get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                step_size = float(f.get("stepSize", 0.0))
                break

        if qty < min_qty:
            log(f"[validate_qty] Qty {qty} < min_qty {min_qty} for {symbol}", level="WARNING")
            return None

        steps = round(qty / step_size)
        adjusted_qty = round(steps * step_size, precision)

        log(f"[validate_qty] Adjusted qty from {qty} to {adjusted_qty} for {symbol}", level="DEBUG")

        if adjusted_qty < min_qty:
            log(f"[validate_qty] Adjusted qty {adjusted_qty} < min_qty {min_qty} for {symbol}", level="WARNING")
            return None

        return adjusted_qty

    except (KeyError, ValueError, TypeError) as e:
        log(f"[validate_qty] Failed to validate qty for {symbol}: {e}", level="ERROR")
        return None
