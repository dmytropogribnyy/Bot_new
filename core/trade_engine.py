# trade_engine.py

import threading
import time
import traceback
from threading import Lock

import pandas as pd
import ta

from common.config_loader import (
    ADX_FLAT_THRESHOLD,
    ADX_TREND_THRESHOLD,
    AUTO_CLOSE_PROFIT_THRESHOLD,
    AUTO_TP_SL_ENABLED,
    BONUS_PROFIT_THRESHOLD,
    BREAKOUT_DETECTION,
    DRY_RUN,
    ENABLE_BREAKEVEN,
    ENABLE_TRAILING,
    MAX_MARGIN_PERCENT,
    MAX_OPEN_ORDERS,
    MAX_POSITIONS,
    MICRO_PROFIT_ENABLED,
    MICRO_PROFIT_THRESHOLD,
    MICRO_TRADE_SIZE_THRESHOLD,
    MICRO_TRADE_TIMEOUT_MINUTES,
    MIN_NOTIONAL_OPEN,
    MIN_NOTIONAL_ORDER,
    SHORT_TERM_MODE,
    SOFT_EXIT_ENABLED,
    TAKER_FEE_RATE,
    TP1_PERCENT,
    USE_TESTNET,
    get_priority_small_balance_pairs,
)
from common.leverage_config import LEVERAGE_MAP
from core.binance_api import fetch_ohlcv
from core.exchange_init import exchange
from core.position_manager import can_open_new_position
from core.risk_utils import get_adaptive_risk_percent
from core.tp_utils import calculate_tp_levels
from telegram.telegram_utils import send_telegram_message
from utils_core import extract_symbol, get_cached_balance, get_cached_positions, initialize_cache, is_optimal_trading_hour, load_state, safe_call_retry
from utils_logging import log, now

###############################################################################
#                     TRADE INFO MANAGER (GLOBAL STORAGE)                     #
###############################################################################


class TradeInfoManager:
    def __init__(self):
        self._trades = {}
        self._lock = threading.Lock()

    def add_trade(self, symbol, trade_data):
        symbol = extract_symbol(symbol)
        with self._lock:
            self._trades[symbol] = trade_data

    def get_trade(self, symbol):
        symbol = extract_symbol(symbol)
        with self._lock:
            return self._trades.get(symbol)

    def update_trade(self, symbol, key, value):
        symbol = extract_symbol(symbol)
        with self._lock:
            if symbol in self._trades:
                self._trades[symbol][key] = value

    def remove_trade(self, symbol):
        symbol = extract_symbol(symbol)
        with self._lock:
            return self._trades.pop(symbol, None)

    def get_last_closed_time(self, symbol):
        symbol = extract_symbol(symbol)
        with self._lock:
            return self._trades.get(symbol, {}).get("last_closed_time", None)

    def set_last_closed_time(self, symbol, timestamp):
        symbol = extract_symbol(symbol)
        with self._lock:
            if symbol not in self._trades:
                self._trades[symbol] = {}
            self._trades[symbol]["last_closed_time"] = timestamp


###############################################################################
#                             GLOBAL VARIABLES                                #
###############################################################################

trade_manager = TradeInfoManager()
monitored_stops = {}
monitored_stops_lock = threading.Lock()

open_positions_count = 0
dry_run_positions_count = 0
open_positions_lock = threading.Lock()

logged_trades = set()
logged_trades_lock = Lock()


###############################################################################
#                               CORE METHODS                                  #
###############################################################################


def close_trade_and_cancel_orders(binance_client, symbol, side, quantity, reduce_only=True):
    """
    Close a position with a market order and cancel all related orders.
    """
    try:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"

        # Cancel open orders
        try:
            binance_client.futures_cancel_all_open_orders(symbol=symbol.replace("/", ""))
            log(f"✅ Canceled all open orders for {symbol}.", level="INFO")
        except Exception as e:
            log(f"❌ Error canceling orders for {symbol}: {str(e)}", level="WARNING")

        # Then close the position
        binance_client.futures_create_order(
            symbol=symbol.replace("/", ""),
            side=close_side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=reduce_only,
        )
        log(f"✅ Closed position {symbol} — {quantity} units by MARKET.", level="INFO")

    except Exception as e:
        log(f"❌ Error while closing {symbol}: {str(e)}", level="ERROR")


def safe_close_trade(binance_client, symbol, trade_data, reason="manual"):
    """
    Safely close a trade by cancelling all orders and closing the position.
    """
    symbol = extract_symbol(symbol)

    try:
        side = trade_data["side"]
        quantity = trade_data["quantity"]
        entry_price = trade_data.get("entry", 0)

        # Current price
        ticker = safe_call_retry(exchange.fetch_ticker, symbol)
        exit_price = ticker["last"] if ticker else None

        # Cancel + close
        close_trade_and_cancel_orders(
            binance_client=binance_client,
            symbol=symbol,
            side=side,
            quantity=quantity,
        )

        # Record result BEFORE removing from manager
        if exit_price:
            if side.lower() == "buy":
                final_pnl = (exit_price - entry_price) * quantity
            else:
                final_pnl = (entry_price - exit_price) * quantity

            log(f"[SafeClose] {symbol} closed with PnL = {final_pnl:.2f} USDC", level="INFO")
            record_trade_result(symbol, side, entry_price, exit_price, reason)

        trade_manager.remove_trade(symbol)
        log(f"✅ Safe close complete for {symbol} (reason: {reason})", level="INFO")

    except Exception as e:
        log(f"❌ Error during safe close for {symbol}: {str(e)}", level="ERROR")


def calculate_risk_amount(balance, risk_percent=None, symbol=None, atr_percent=None, volume_usdc=None):
    """
    Упрощённый расчёт risk amount без score.
    """
    from common.config_loader import trade_stats

    # Win streak
    win_streak = trade_stats.get("streak_win", 0)

    if risk_percent is None:
        risk_percent = get_adaptive_risk_percent(
            balance,
            atr_percent=atr_percent,
            volume_usdc=volume_usdc,
            win_streak=win_streak,
        )

    log(f"Using risk percentage: {risk_percent*100:.2f}% for balance: {balance:.2f} USDC", level="DEBUG")
    return balance * risk_percent


def calculate_position_size(entry_price, stop_price, risk_amount, symbol=None):
    """
    Calculate position size with graduated risk adjustment.
    """
    if entry_price <= 0 or stop_price <= 0:
        return 0

    risk_factor = 1.0
    if symbol:
        from core.fail_stats_tracker import get_symbol_risk_factor

        rf, _ = get_symbol_risk_factor(symbol)
        risk_factor = rf
        if risk_factor < 1.0:
            log(f"Applied risk reduction to {symbol}: {risk_factor:.2f}x position size", level="INFO")

    adjusted_risk = risk_amount * risk_factor
    price_delta = abs(entry_price - stop_price)
    if price_delta == 0:
        return 0

    position_size = adjusted_risk / price_delta
    return position_size


def get_position_size(symbol):
    """
    Return open position size (contracts).
    """
    try:
        positions = get_cached_positions()
        for pos in positions:
            if pos["symbol"] == symbol and float(pos.get("contracts", 0)) > 0:
                return float(pos["contracts"])
    except Exception as e:
        log(f"Error in get_position_size for {symbol}: {e}", level="ERROR")
    return 0


def get_market_regime(symbol):
    """
    Enhanced market regime detection with breakout support.
    """
    try:
        ohlcv = fetch_ohlcv(symbol, timeframe="15m", limit=50)

        # Добавлена проверка: если ohlcv не является списком или мало данных → нейтральный режим
        if not isinstance(ohlcv, list) or len(ohlcv) < 28:
            log(f"{symbol} ⚠️ Insufficient or invalid OHLCV data => neutral", level="WARNING")
            return "neutral"

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]

        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})

        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if adx_series.isna().all():
            log(f"{symbol} ⚠️ ADX calc returned NaN => neutral", level="WARNING")
            return "neutral"

        adx = adx_series.iloc[-1]

        bb = ta.volatility.BollingerBands(df["close"], window=20)
        bb_width = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / df["close"].iloc[-1]

        log(f"{symbol} 🔍 Market regime: ADX={adx:.2f}, BBW={bb_width:.4f}", level="DEBUG")

        if BREAKOUT_DETECTION and bb_width > 0.05 and adx > 20:
            log(f"{symbol} 🔍 Breakout!", level="INFO")
            return "breakout"
        elif adx > ADX_TREND_THRESHOLD:
            return "trend"
        elif adx < ADX_FLAT_THRESHOLD:
            return "flat"
        else:
            return "neutral"

    except Exception as e:
        log(f"[ERROR] Market regime for {symbol}: {e}", level="ERROR")
        return "neutral"


###############################################################################
#                                ENTER TRADE                                  #
###############################################################################


def enter_trade(symbol, side, qty, is_reentry=False, breakdown=None, pair_type="unknown"):
    """
    Основная функция входа в сделку.
    - После create_safe_market_order(...) в любом случае вызывается add_trade(...),
      чтобы сделка появилась в trade_manager.
    - Сразу после add_trade(...) сохраняем data/active_trades.json,
      чтобы при перезапуске бота сделки восстанавливались.
    """
    symbol = extract_symbol(symbol)
    if breakdown:
        log(f"[Breakdown] {symbol} entry breakdown: {breakdown}", level="DEBUG")

    state = load_state()
    if state.get("stopping"):
        log("Cannot enter trade: bot is stopping.", level="WARNING")
        return

    # Торговые часы
    if SHORT_TERM_MODE and not is_optimal_trading_hour():
        balance = get_cached_balance()
        if balance < 120 and symbol in get_priority_small_balance_pairs():
            log(f"{symbol} Priority pair allowed during non-optimal hours", level="INFO")
        else:
            log(f"{symbol} ⏰ Skipping trade during non-optimal hours", level="INFO")
            send_telegram_message(f"⏰ Skipping {symbol}: non-optimal trading hours", force=True)
            return

    balance = get_cached_balance()
    if not can_open_new_position(balance):
        log(f"[Skip] Position limit reached for balance: {balance:.2f} USDC", level="INFO")
        return

    try:
        positions = exchange.fetch_positions()
        active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
        if active_positions >= MAX_POSITIONS:
            log(f"[Skipping {symbol}] Max positions ({MAX_POSITIONS}) reached. Active: {active_positions}", level="INFO")
            return
    except Exception as e:
        log(f"[Enter Trade] Failed to fetch positions for {symbol}: {e}", level="ERROR")
        return

    account_category = "Small" if balance < 120 else "Medium" if balance < 300 else "Standard"
    is_priority_pair = symbol in get_priority_small_balance_pairs() if account_category in ("Small", "Medium") else False

    global open_positions_count, dry_run_positions_count
    try:
        with open_positions_lock:
            if DRY_RUN:
                dry_run_positions_count += 1
            else:
                open_positions_count += 1

        ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"enter_trade {symbol}")
        if not ticker:
            log(f"[ERROR] Failed to fetch ticker for {symbol}", level="ERROR")
            send_telegram_message(f"⚠️ Failed to fetch ticker for {symbol}", force=True)
            return

        entry_price = ticker["last"]
        start_time = now()

        if is_reentry:
            if get_position_size(symbol) > 0:
                log(f"Skipping re-entry for {symbol}: position already open", level="WARNING")
                return
            log(f"Re-entry triggered for {symbol} at {entry_price}", level="INFO")
            send_telegram_message(f"🔄 Re-entry {symbol} @ {entry_price}", force=True)

        # Логируем компоненты сигнала
        if breakdown:
            from core.component_tracker import log_component_data

            log_component_data(symbol, breakdown, is_successful=True)

        # ===== Расчёт и проверка notional, qty и т.д. =====
        leverage_key = symbol.split(":")[0].replace("/", "") if USE_TESTNET else symbol.replace("/", "")
        leverage = LEVERAGE_MAP.get(leverage_key, 1)
        adjusted_qty = qty * leverage

        from core.fail_stats_tracker import get_symbol_risk_factor

        rf, _ = get_symbol_risk_factor(symbol)
        risk_factor = rf
        risk_percent = get_adaptive_risk_percent(balance)
        adjusted_risk = balance * risk_percent * risk_factor
        log(f"🧠 {symbol} | risk_factor={risk_factor:.2f} → scaled risk={adjusted_risk:.2f} USDC", level="INFO")

        if risk_factor < 0.9:
            from telegram.telegram_utils import escape_markdown_v2

            send_telegram_message(
                f"🔹 *{escape_markdown_v2(symbol)}* opened with `risk_factor={risk_factor:.2f}`\n" f"💰 Adjusted position risk: *{adjusted_risk:.2f} USDC*",
                force=True,
            )

        notional = adjusted_qty * entry_price
        while notional < MIN_NOTIONAL_OPEN:
            adjusted_qty *= 1.1
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Adjusted qty for {symbol} to {adjusted_qty:.6f} to meet min notional {notional:.2f}", level="DEBUG")

        if notional < MIN_NOTIONAL_OPEN:
            log(f"{symbol} ⚠️ Notional too small: {notional:.2f} < {MIN_NOTIONAL_OPEN}", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
            return

        account_balance = get_cached_balance()
        max_allowed_position = account_balance * 0.6
        notional = adjusted_qty * entry_price
        if notional > max_allowed_position:
            old_qty = adjusted_qty
            adjusted_qty = max_allowed_position / entry_price
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Position size for {symbol} reduced from {old_qty:.6f} to {adjusted_qty:.6f} (over 60% balance)", level="WARNING")

        from core.risk_utils import check_capital_utilization

        if not check_capital_utilization(account_balance, notional):
            log(f"[Enter Trade] Skipping {symbol} due to capital utilization risk", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: capital utilization limit exceeded", force=True)
            return

        balance = get_cached_balance()
        max_margin = balance * MAX_MARGIN_PERCENT
        required_margin = notional / leverage
        if required_margin > max_margin * 0.92:
            adjusted_qty = (max_margin * leverage * 0.92) / entry_price
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Adjusted qty for {symbol} -> {adjusted_qty:.6f} to meet max margin limit", level="DEBUG")

        precision = exchange.markets[symbol]["precision"]["amount"]
        min_qty = exchange.markets[symbol]["limits"]["amount"]["min"]
        adjusted_qty = round(adjusted_qty, precision)
        if adjusted_qty < min_qty:
            adjusted_qty = max(min_qty, adjusted_qty)
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Adjusted qty for {symbol} -> {adjusted_qty:.6f} to meet min qty {min_qty}", level="DEBUG")
        elif adjusted_qty == 0:
            adjusted_qty = 10**-precision
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Adjusted qty for {symbol} -> {adjusted_qty:.6f} (precision {precision})", level="DEBUG")

        if notional < MIN_NOTIONAL_OPEN:
            log(f"{symbol} ⚠️ Notional too small after final adjustments: {notional:.2f} < {MIN_NOTIONAL_OPEN}", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
            return

        qty = adjusted_qty

        open_orders = exchange.fetch_open_orders(symbol)
        if len(open_orders) >= MAX_OPEN_ORDERS:
            log(f"[TP/SL] Skipping {symbol} — max open orders ({MAX_OPEN_ORDERS}) reached", level="DEBUG")
            return

        if DRY_RUN:
            # DRY RUN: просто логируем и регистрируем сделку
            log(f"[DRY_RUN] Entering {side.upper()} on {symbol} @ {entry_price:.5f} (qty: {qty:.2f})", level="INFO")
            msg = f"DRY-RUN {'REENTRY ' if is_reentry else ''}{side.upper()} {symbol}@{entry_price:.2f} Qty:{qty:.3f}"
            send_telegram_message(msg, force=True, parse_mode=None)

            trade_data = {
                "symbol": symbol,
                "side": side,
                "entry": round(entry_price, 4),
                "qty": qty,
                "tp1_hit": False,
                "tp2_hit": False,
                "sl_hit": False,
                "soft_exit_hit": False,
                "start_time": start_time,
                "account_category": account_category,
                "commission": 0.0,
                "net_profit_tp1": 0.0,
                "market_regime": None,
                "quantity": qty,
                "breakdown": breakdown or {},
                "priority_pair": is_priority_pair,
                "pair_type": pair_type,
            }
            trade_manager.add_trade(symbol, trade_data)

            # Сохраняем active_trades.json
            import json
            from pathlib import Path

            Path("data").mkdir(exist_ok=True)
            with open("data/active_trades.json", "w", encoding="utf-8") as f:
                json.dump(trade_manager._trades, f, indent=2, default=str)
            return

        else:
            # REAL TRADE
            try:
                from threading import Thread

                from core.binance_api import create_safe_market_order

                trade_data = {
                    "symbol": symbol,
                    "side": side,
                    "entry": round(entry_price, 4),
                    "qty": qty,
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "sl_hit": False,
                    "soft_exit_hit": False,
                    "start_time": start_time,
                    "account_category": account_category,
                    "commission": 0.0,
                    "net_profit_tp1": 0.0,
                    "market_regime": None,
                    "quantity": qty,
                    "breakdown": breakdown or {},
                    "priority_pair": is_priority_pair,
                    "pair_type": pair_type,
                }

                result = create_safe_market_order(symbol, side.lower(), qty)
                trade_manager.add_trade(symbol, trade_data)

                # Сохраняем active_trades.json
                import json
                from pathlib import Path

                Path("data").mkdir(exist_ok=True)
                with open("data/active_trades.json", "w", encoding="utf-8") as f:
                    json.dump(trade_manager._trades, f, indent=2, default=str)

                if not result["success"]:
                    error_msg = result["error"]
                    log(f"[Enter Trade] Market order failed for {symbol}: {error_msg}", level="ERROR")
                    send_telegram_message(f"❌ Failed to open trade {symbol}: {error_msg}", force=True)
                    return
                else:
                    log(f"[Enter Trade] Opened position for {symbol}: qty={qty}, entry={entry_price:.4f}", level="INFO")
                    send_telegram_message(
                        f"🚀 ENTER {symbol} {side.upper()} qty={qty:.4f} @ {entry_price:.4f}",
                        force=True,
                    )
                    Thread(target=run_auto_profit_exit, args=(symbol, side, entry_price), daemon=True).start()
                    log(f"[Auto-Profit] Thread started for {symbol}", level="DEBUG")

            except Exception as e:
                log(f"[Enter Trade] Exception opening position for {symbol}: {str(e)}", level="ERROR")
                send_telegram_message(f"❌ Exception in open trade {symbol}: {str(e)}", force=True)
                return

        # ===== Дальше рассчитываем TP/SL =====
        regime = get_market_regime(symbol) if AUTO_TP_SL_ENABLED else None
        tp1_price, tp2_price, sl_price, qty_tp1_share, qty_tp2_share = calculate_tp_levels(entry_price, side, regime)
        if any(v is None for v in [tp1_price, sl_price]):
            log(f"⚠️ Skipping TP/SL for {symbol} — invalid prices", level="ERROR")
            send_telegram_message(f"⚠️ Invalid TP/SL for {symbol}", force=True)
            return

        precision = exchange.markets[symbol]["precision"]["amount"]
        qty_tp1 = round(qty * qty_tp1_share, precision)
        qty_tp2 = round(qty * qty_tp2_share, precision)

        # Проверка notional для TP
        if qty_tp1 * tp1_price < MIN_NOTIONAL_ORDER:
            log(f"[Enter Trade] TP1 notional too small for {symbol}", level="WARNING")
            qty_tp1 = 0
        if tp2_price and qty_tp2 * tp2_price < MIN_NOTIONAL_ORDER:
            log(f"[Enter Trade] TP2 notional too small for {symbol}", level="WARNING")
            qty_tp2 = 0

        commission_est = 2 * (qty * entry_price * TAKER_FEE_RATE)
        net_profit_tp1 = (qty_tp1 * abs(tp1_price - entry_price)) - commission_est

        trade_manager.update_trade(symbol, "tp1_price", round(tp1_price, 5))
        trade_manager.update_trade(symbol, "tp2_price", round(tp2_price, 5) if tp2_price else None)
        trade_manager.update_trade(symbol, "sl_price", round(sl_price, 5))
        trade_manager.update_trade(symbol, "net_profit_tp1", net_profit_tp1)

        from core.order_utils import create_post_only_limit_order

        try:
            if qty_tp1 > 0:
                create_post_only_limit_order(symbol, "sell" if side.lower() == "buy" else "buy", qty_tp1, tp1_price)
            if tp2_price and qty_tp2 > 0:
                create_post_only_limit_order(symbol, "sell" if side.lower() == "buy" else "buy", qty_tp2, tp2_price)

            safe_call_retry(
                exchange.create_order,
                symbol,
                "STOP_MARKET",
                "sell" if side.lower() == "buy" else "buy",
                qty,
                params={"stopPrice": round(sl_price, 4), "reduceOnly": True},
                label=f"create_stop_order {symbol}",
            )
        except Exception as e:
            log(f"[Enter Trade] Failed to place TP/SL for {symbol}: {e}", level="ERROR")
            send_telegram_message(f"⚠️ Failed to place TP/SL for {symbol}: {e}", force=True)

        # monitor logic
        track_stop_loss(symbol, side, entry_price, qty, start_time)

        if ENABLE_TRAILING:
            threading.Thread(
                target=run_adaptive_trailing_stop,
                args=(symbol, side, entry_price),
                daemon=True,
            ).start()

        if ENABLE_BREAKEVEN:
            threading.Thread(
                target=run_break_even,
                args=(symbol, side, entry_price, TP1_PERCENT),
                daemon=True,
            ).start()

        if SOFT_EXIT_ENABLED:
            threading.Thread(
                target=run_soft_exit,
                args=(symbol, side, entry_price, TP1_PERCENT, qty),
                daemon=True,
            ).start()

        if MICRO_PROFIT_ENABLED:
            threading.Thread(
                target=run_micro_profit_optimizer,
                args=(symbol, side, entry_price, qty, start_time),
                daemon=True,
            ).start()
            log(f"[DEBUG] Started micro-profit monitor for {symbol}", level="DEBUG")

        threading.Thread(
            target=monitor_active_position,
            args=(symbol, side, entry_price, qty, start_time),
            daemon=True,
        ).start()
        log(f"[DEBUG] Started dynamic position management for {symbol}", level="DEBUG")

    except Exception as e:
        log(f"[Enter Trade] Unexpected error for {symbol}: {str(e)}", level="ERROR")
        send_telegram_message(f"❌ Unexpected error in trade {symbol}: {str(e)}", force=True)
    finally:
        with open_positions_lock:
            if DRY_RUN:
                dry_run_positions_count -= 1
            else:
                open_positions_count -= 1


def track_stop_loss(symbol, side, entry_price, qty, opened_at):
    with monitored_stops_lock:
        monitored_stops[symbol] = {
            "side": side,
            "entry": entry_price,
            "qty": qty,
            "opened_at": opened_at,
        }


###############################################################################
#                               AUX METHODS                                   #
###############################################################################


def run_break_even(symbol, side, entry_price, tp_percent, check_interval=5):
    """
    Optional. If you want break-even logic, keep it here.
    """
    pass  # (omitted for brevity if not used)


def run_adaptive_trailing_stop(symbol, side, entry_price, check_interval=5, pair_type="fixed"):
    """
    Optional trailing stop logic.
    """
    pass  # (omitted for brevity if not used)


def run_soft_exit(symbol, side, entry_price, tp1_percent, qty, check_interval=5):
    """
    Optional partial exit logic.
    """
    pass  # (omitted for brevity if not used)


###############################################################################
#                     RECORDING TRADE RESULTS / CLOSING                       #
###############################################################################


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    """
    При финальном закрытии сделки (TP, SL, manual, trailing и т.д.):
    - Считает финальный PnL, комиссию,
    - Записывает в tp_performance.csv через log_trade_result(...)
    - Шлёт сообщение в Telegram,
    - Удаляет сделку из trade_manager.
    """
    symbol = extract_symbol(symbol)

    global open_positions_count, dry_run_positions_count

    caller_stack = traceback.format_stack()[-2]
    log(f"[DEBUG] record_trade_result for {symbol}, {result_type}, caller: {caller_stack}", level="DEBUG")

    trade_key = f"{symbol}_{result_type}_{entry_price}_{round(exit_price, 4)}"
    with logged_trades_lock:
        if trade_key in logged_trades:
            log(f"[DEBUG] Skipping duplicate logging {symbol}, {result_type}", level="DEBUG")
            return
        logged_trades.add(trade_key)

    # Обновляем счётчики
    with open_positions_lock:
        if DRY_RUN:
            dry_run_positions_count -= 1
        else:
            open_positions_count -= 1

    # Достаём trade
    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"⚠️ No trade info for {symbol} — cannot record result", level="WARNING")
        return

    # Проверяем "soft_exit", SL/TP
    final_result_type = result_type
    if trade.get("soft_exit_hit", False) and result_type in ["manual", "stop"]:
        final_result_type = "soft_exit"

    if trade.get("tp1_hit", False) or trade.get("tp2_hit", False):
        exit_reason = "tp"
    elif result_type == "sl":
        exit_reason = "sl"
    else:
        exit_reason = "flat"

    # Считаем PnL
    duration = int((time.time() - trade["start_time"].timestamp()) / 60)
    pnl = ((exit_price - entry_price) / entry_price) * 100
    if side.lower() == "sell":
        pnl *= -1

    breakdown = trade.get("breakdown", {})
    commission = float(trade.get("commission", 0.0))
    qty = float(trade.get("qty", 0.0))
    atr = float(trade.get("atr", 0.0))
    pair_type = trade.get("pair_type", "unknown")

    absolute_profit = (exit_price - entry_price) * qty if side.lower() == "buy" else (entry_price - exit_price) * qty
    net_absolute_profit = absolute_profit - commission

    # component_tracker
    from core.component_tracker import log_component_data

    is_successful = (exit_reason == "tp") and (net_absolute_profit > 0)
    log_component_data(symbol, breakdown, is_successful=is_successful)

    trade.get("account_category", "Standard")

    # Запись в CSV
    from tp_logger import log_trade_result as low_level_csv_writer

    net_pnl_percent = 0.0
    if qty > 0 and entry_price > 0:
        net_pnl_percent = (net_absolute_profit / abs(entry_price * qty)) * 100

    low_level_csv_writer(
        symbol=symbol,
        direction=side.upper(),
        entry_price=entry_price,
        exit_price=exit_price,
        qty=qty,
        tp1_hit=trade.get("tp1_hit", False),
        tp2_hit=trade.get("tp2_hit", False),
        sl_hit=(result_type == "sl"),
        pnl_percent=round(pnl, 2),
        duration_minutes=duration,
        result_type=final_result_type,
        exit_reason=exit_reason,
        atr=atr,
        pair_type=pair_type,
        commission=commission,
        net_pnl=round(net_pnl_percent, 2),
        absolute_profit=round(net_absolute_profit, 2),
    )

    # Telegram уведомление
    msg = (
        f"📤 *Trade Closed* [{final_result_type.upper()} / {exit_reason.upper()}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(pnl, 2)}% | ${round(net_absolute_profit, 2)} USDC\n"
        f"• Held: {duration} min"
    )
    send_telegram_message(msg, force=True)

    # Удаляем сделку
    trade_manager.remove_trade(symbol)
    log(f"[DEBUG] Trade {symbol} removed after logging", level="DEBUG")


def close_dry_trade(symbol):
    """
    Закрываем DRY-run сделку сразу, если нужно принудительно.
    """
    if DRY_RUN:
        trade = trade_manager.get_trade(symbol)
        if trade:
            ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")
            if not ticker:
                return
            exit_price = ticker["last"]
            record_trade_result(symbol, trade["side"], trade["entry"], exit_price, "manual")
            log(f"[DRY] Closed {symbol} at {exit_price}", level="INFO")
            send_telegram_message(f"DRY RUN: Closed {symbol} at {exit_price}", force=True)
            trade_manager.set_last_closed_time(symbol, time.time())


def close_real_trade(symbol):
    """
    Принудительно закрываем реальную сделку.
    Сначала отменяем ордера, затем маркет-закрытие, затем логирование через record_trade_result(...).
    """
    symbol = extract_symbol(symbol)

    state = load_state()
    trade = trade_manager.get_trade(symbol)

    if not trade:
        if not state.get("stopping") and not state.get("shutdown"):
            log(f"[SmartSwitch] No active trade for {symbol}", level="WARNING")
        return

    try:
        # 1) Отмена всех ордеров (TP/SL)
        open_orders = exchange.fetch_open_orders(symbol)
        for order in open_orders:
            try:
                exchange.cancel_order(order["id"], symbol)
                log(f"[Close Trade] Cancelled order {order['id']} for {symbol}", level="INFO")
            except Exception as e:
                log(f"[Close Trade] Failed to cancel order {order['id']} for {symbol}: {e}", level="ERROR")
                send_telegram_message(f"❌ Failed to cancel order for {symbol}: {str(e)}", force=True)

        # 2) Проверка позиции
        positions = exchange.fetch_positions()
        position = next((p for p in positions if p["symbol"] == symbol and float(p.get("contracts", 0)) > 0), None)

        if position:
            side = trade["side"]
            qty = float(position["contracts"])
            ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")
            exit_price = ticker["last"] if ticker else trade["entry"]

            if not DRY_RUN:
                if side.lower() == "buy":
                    safe_call_retry(exchange.create_market_sell_order, symbol, qty, label=f"close_sell {symbol}")
                else:
                    safe_call_retry(exchange.create_market_buy_order, symbol, qty, label=f"close_buy {symbol}")

            log(f"[SmartSwitch] Closed {symbol} at {exit_price}, qty={qty}", level="INFO")

            # 3) Логирование через record_trade_result (вместо log_trade_result)
            record_trade_result(symbol, side, trade["entry"], exit_price, result_type="manual")

        else:
            log(f"[SmartSwitch] No open position for {symbol} on exchange", level="WARNING")

        # 4) Завершаем
        trade_manager.remove_trade(symbol)
        trade_manager.set_last_closed_time(symbol, time.time())
        initialize_cache()

    except Exception as e:
        log(f"[SmartSwitch] Error closing real trade {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trade {symbol}: {str(e)}", force=True)


def open_real_trade(symbol, direction, qty, entry_price):
    """
    Упрощённая версия входа без сложных расчётов (если нужно).
    """
    try:
        side = "buy" if direction.lower() == "buy" else "sell"
        order = exchange.create_market_order(symbol, side, qty)
        log(f"[Open Trade] Opened {direction} for {symbol}: qty={qty}, entry={entry_price}", level="INFO")
        initialize_cache()
        return order
    except Exception as e:
        log(f"[Open Trade] Failed for {symbol}: {e}", level="ERROR")
        raise


###############################################################################
#                            AUTO PROFIT METHODS                              #
###############################################################################


def run_auto_profit_exit(symbol, side, entry_price, check_interval=5):
    """
    Пример автозакрытия при достижении заданного профита.
    Добавлен вызов record_trade_result(...) после закрытия сделки.
    Используем already fetched current_price вместо get_current_price(symbol).
    """
    symbol = extract_symbol(symbol)

    log(f"[Auto-Profit] Starting profit check for {symbol}", level="DEBUG")

    while True:
        try:
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"[Auto-Profit] No trade for {symbol}, stop thread", level="INFO")
                break

            # Если уже tp1_hit => прерываем (пусть TP2/SL дальше обрабатывает)
            if trade.get("tp1_hit"):
                log(f"[Auto-Profit] TP1 for {symbol} already hit; let TP2 handle", level="INFO")
                break

            # Лимит по времени (например, 60 мин)
            trade_start = trade.get("start_time")
            if trade_start:
                duration = (time.time() - trade_start.timestamp()) / 60
                if duration > 60:
                    log(f"[Auto-Profit] 60-min limit for {symbol} exceeded, stop auto-profit", level="INFO")
                    break

            # Проверяем, не закрыта ли позиция вручную
            position = get_position_size(symbol)
            if position <= 0:
                log(f"[Auto-Profit] {symbol} already closed, stopping thread", level="INFO")
                break

            # Текущая цена
            ticker = safe_call_retry(exchange.fetch_ticker, symbol)
            if not ticker:
                break
            current_price = ticker["last"]

            # Считаем profit %
            side_lower = side.lower()
            if side_lower == "buy":
                profit_percentage = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_percentage = ((entry_price - current_price) / entry_price) * 100

            log(f"[Auto-Profit] {symbol} current profit: {profit_percentage:.2f}%", level="DEBUG")

            # Если достигли BONUS_PROFIT_THRESHOLD => закрываем
            if profit_percentage >= BONUS_PROFIT_THRESHOLD:
                log(f"🎉 BONUS PROFIT! Auto-closing {symbol} at +{profit_percentage:.2f}%", level="INFO")

                # Закрываем (safe_close_trade(...) не вызывает record_trade_result(...)?)
                safe_close_trade(exchange, symbol, trade, reason="bonus_profit")

                # Фиксируем результат
                record_trade_result(
                    symbol,
                    side,
                    entry_price,
                    current_price,  # используем уже известный current_price
                    result_type="tp",  # или "bonus_profit"
                )
                send_telegram_message(f"🎉 *Bonus Profit!* {symbol} closed at +{profit_percentage:.2f}%!")
                break

            # Аналогично, если достигли AUTO_CLOSE_PROFIT_THRESHOLD => закрываем
            elif profit_percentage >= AUTO_CLOSE_PROFIT_THRESHOLD:
                log(f"✅ Auto-closing {symbol} at +{profit_percentage:.2f}%", level="INFO")

                safe_close_trade(exchange, symbol, trade, reason="auto_profit")

                record_trade_result(
                    symbol,
                    side,
                    entry_price,
                    current_price,  # опять же, используем current_price
                    result_type="tp",
                )
                send_telegram_message(f"✅ *Auto-closed* {symbol} at +{profit_percentage:.2f}%!")
                break

            # иначе ждём и проверяем снова
            time.sleep(check_interval)

        except Exception as e:
            log(f"[ERROR] Auto-profit {symbol}: {e}", level="ERROR")
            break


def check_auto_profit(trade, threshold=AUTO_CLOSE_PROFIT_THRESHOLD):
    """
    Если где-то ещё вызывается: проверяем, достигнут ли threshold.
    """
    pass  # (можно не менять, если не используется напрямую)


###############################################################################
#                          MICRO PROFIT / MONITORING                          #
###############################################################################


def run_micro_profit_optimizer(symbol, side, entry_price, qty, start_time, check_interval=5):
    """
    Если позиция очень мала (micro), закрывать при малом профите или по тайм-ауту.
    """
    if not MICRO_PROFIT_ENABLED:
        return

    balance = get_cached_balance()
    position_value = qty * entry_price
    position_percentage = position_value / balance if balance > 0 else 0

    if position_percentage >= MICRO_TRADE_SIZE_THRESHOLD:
        log(f"{symbol} Not a micro-trade ({position_percentage:.2%} of balance)", level="DEBUG")
        return

    base_threshold = MICRO_PROFIT_THRESHOLD
    if position_percentage < 0.15:
        profit_threshold = base_threshold
    elif position_percentage < 0.25:
        profit_threshold = base_threshold * 1.33
    else:
        profit_threshold = base_threshold * 1.67

    log(f"{symbol} 🔍 Starting micro-profit optimizer with {profit_threshold:.1f}% threshold", level="INFO")

    while True:
        try:
            position_size = get_position_size(symbol)
            if position_size <= 0:
                log(f"{symbol} position closed, end micro-profit optimizer", level="DEBUG")
                break

            elapsed_minutes = (time.time() - start_time.timestamp()) / 60
            if elapsed_minutes >= MICRO_TRADE_TIMEOUT_MINUTES:
                ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"micro_profit_optimizer {symbol}")
                if not ticker:
                    log(f"Failed to fetch price for {symbol} in micro-profit", level="WARNING")
                    break

                current_price = ticker["last"]
                if side.lower() == "buy":
                    profit_percent = ((current_price - entry_price) / entry_price) * 100
                else:
                    profit_percent = ((entry_price - current_price) / entry_price) * 100

                if profit_percent >= profit_threshold:
                    log(f"{symbol} 🕒 Micro-trade timeout => +{profit_percent:.2f}% profit", level="INFO")
                    trade_data = trade_manager.get_trade(symbol)
                    if trade_data:
                        safe_close_trade(exchange, symbol, trade_data, reason="micro_profit")
                        send_telegram_message(f"⏰ Micro-profit: {symbol} closed +{profit_percent:.2f}%", force=True)
                else:
                    log(f"{symbol} ❎ Micro-trade timeout => only {profit_percent:.2f}%, stopping", level="INFO")
                break

            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Micro-profit {symbol}: {e}", level="ERROR")
            break


def monitor_active_position(symbol, side, entry_price, initial_qty, start_time):
    """
    Dynamic position management + Telegram уведомления по TP1/TP2/SL.
    Добавлен тайм-аут (runtime_config["max_hold_minutes"]): если сделка висит дольше, форсированно закрывается.
    При фактическом закрытии (current_position <= 0) вызываем record_trade_result(...),
    используя последний актуальный current_price, полученный из fetch_ticker.
    """
    from utils_core import get_runtime_config

    last_check_time = time.time()
    position_increased = False
    position_reduced = False
    last_fetched_price = entry_price

    MAX_HOLD_MINUTES = get_runtime_config().get("max_hold_minutes", 90)

    while True:
        try:
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"{symbol} => trade removed, stop dynamic monitoring", level="DEBUG")
                break

            current_position = get_position_size(symbol)
            if current_position <= 0:
                log(f"[Monitor] {symbol} => position closed => record result", level="INFO")

                if trade.get("sl_hit"):
                    reason_type = "sl"
                elif trade.get("tp1_hit") or trade.get("tp2_hit"):
                    reason_type = "tp"
                else:
                    reason_type = "manual"

                record_trade_result(symbol, side, entry_price, last_fetched_price, result_type=reason_type)
                break

            # Тайм-аут
            duration_minutes = (time.time() - start_time.timestamp()) / 60
            if duration_minutes >= MAX_HOLD_MINUTES:
                log(f"{symbol} ⏱ Timed out after {duration_minutes:.0f} min => force close", level="WARNING")
                send_telegram_message(f"⏱ *Timeout Triggered*: {symbol} held >{MAX_HOLD_MINUTES} min\n→ Force-closing trade", force=True)
                from core.trade_engine import close_real_trade

                close_real_trade(symbol)
                break

            tp1_price = trade.get("tp1_price")
            tp2_price = trade.get("tp2_price")
            sl_price = trade.get("sl_price")

            current_time = time.time()
            if current_time - last_check_time < 15:
                time.sleep(0.5)
                continue
            last_check_time = current_time

            price_data = safe_call_retry(exchange.fetch_ticker, symbol, label=f"monitor_position {symbol}")
            if not price_data:
                log(f"{symbol} monitor: failed to fetch price, retry later", level="WARNING")
                time.sleep(5)
                continue

            current_price = price_data["last"]
            last_fetched_price = current_price

            side_lower = side.lower()
            if side_lower == "buy":
                if tp1_price and current_price >= tp1_price and not trade.get("tp1_hit"):
                    trade_manager.update_trade(symbol, "tp1_hit", True)
                    send_telegram_message(f"✅ TP1 HIT: {symbol} @ {current_price:.4f}", force=True)

                if tp2_price and current_price >= tp2_price and not trade.get("tp2_hit"):
                    trade_manager.update_trade(symbol, "tp2_hit", True)
                    send_telegram_message(f"🎯 TP2 HIT: {symbol} @ {current_price:.4f}", force=True)

                if sl_price and current_price <= sl_price and not trade.get("sl_hit"):
                    trade_manager.update_trade(symbol, "sl_hit", True)
                    send_telegram_message(f"🛑 SL HIT: {symbol} @ {current_price:.4f}", force=True)
            else:
                if tp1_price and current_price <= tp1_price and not trade.get("tp1_hit"):
                    trade_manager.update_trade(symbol, "tp1_hit", True)
                    send_telegram_message(f"✅ TP1 HIT: {symbol} @ {current_price:.4f}", force=True)

                if tp2_price and current_price <= tp2_price and not trade.get("tp2_hit"):
                    trade_manager.update_trade(symbol, "tp2_hit", True)
                    send_telegram_message(f"🎯 TP2 HIT: {symbol} @ {current_price:.4f}", force=True)

                if sl_price and current_price >= sl_price and not trade.get("sl_hit"):
                    trade_manager.update_trade(symbol, "sl_hit", True)
                    send_telegram_message(f"🛑 SL HIT: {symbol} @ {current_price:.4f}", force=True)

            # Доп. динамика
            if side_lower == "buy":
                profit_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_percent = ((entry_price - current_price) / entry_price) * 100

            try:
                ohlcv = fetch_ohlcv(symbol, timeframe="5m", limit=12)
                if not isinstance(ohlcv, list) or len(ohlcv) < 6:
                    momentum_increasing = False
                    volume_increasing = False
                    log(f"{symbol} => not enough OHLCV data => skip momentum check", level="DEBUG")
                else:
                    recent_closes = [c[4] for c in ohlcv[-6:]]
                    recent_volumes = [c[5] for c in ohlcv[-6:]]
                    momentum_increasing = False
                    if side_lower == "buy":
                        if recent_closes[-1] > recent_closes[-2] > recent_closes[-3]:
                            momentum_increasing = True
                    else:
                        if recent_closes[-1] < recent_closes[-2] < recent_closes[-3]:
                            momentum_increasing = True

                    recent_avg_volume = sum(recent_volumes[:-1]) / (len(recent_volumes) - 1)
                    current_volume = recent_volumes[-1]
                    volume_increasing = current_volume > (recent_avg_volume * 1.2)
            except Exception as e:
                log(f"[monitor_position] Error analyzing data for {symbol}: {e}", level="ERROR")
                momentum_increasing = False
                volume_increasing = False

            if profit_percent > 1.2 and momentum_increasing and volume_increasing and not position_increased:
                additional_qty = initial_qty * 0.3
                try:
                    balance = get_cached_balance()
                    available_margin = balance * 0.92 - current_position * current_price * 0.5
                    additional_margin_needed = additional_qty * current_price * 0.2

                    if available_margin > additional_margin_needed:
                        safe_call_retry(exchange.create_market_order, symbol, side_lower, additional_qty)
                        position_increased = True
                        log(f"{symbol} 📈 Position increased by 30% at +{profit_percent:.2f}%", level="INFO")
                        send_telegram_message(f"📈 Added to winning position {symbol} +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error increasing position for {symbol}: {e}", level="ERROR")

            elif profit_percent > 0.6 and not momentum_increasing and not position_reduced:
                reduction_qty = current_position * 0.4
                try:
                    safe_call_retry(
                        exchange.create_market_order,
                        symbol,
                        "sell" if side_lower == "buy" else "buy",
                        reduction_qty,
                        {"reduceOnly": True},
                    )
                    position_reduced = True
                    log(f"{symbol} 🔒 Partial profit (40%) at +{profit_percent:.2f}%", level="INFO")
                    send_telegram_message(f"🔒 Partial profit {symbol} +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error partial profit {symbol}: {e}", level="ERROR")

            elif profit_percent > 1.8 and momentum_increasing:
                try:
                    open_orders = exchange.fetch_open_orders(symbol)
                    want_side = "SELL" if side_lower == "buy" else "BUY"
                    tp_orders = [o for o in open_orders if o["type"].upper() == "LIMIT" and o["side"].upper() == want_side]
                    if tp_orders:
                        for order in tp_orders:
                            exchange.cancel_order(order["id"], symbol)

                        new_tp_price = current_price * (1.007 if side_lower == "buy" else 0.993)

                        safe_call_retry(
                            exchange.create_limit_order,
                            symbol,
                            "sell" if side_lower == "buy" else "buy",
                            current_position,
                            new_tp_price,
                            {"reduceOnly": True},
                        )
                        log(f"{symbol} 🎯 Extended TP at +{profit_percent:.2f}%", level="INFO")
                        send_telegram_message(f"🎯 Extended TP for {symbol} +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error extending TP for {symbol}: {e}", level="ERROR")

            time.sleep(1)

        except Exception as e:
            log(f"Error in position monitoring for {symbol}: {e}", level="ERROR")
            time.sleep(5)


def check_micro_profit_exit(symbol, trade_data):
    """
    Automatically close trade if small profit >= MICRO_PROFIT_THRESHOLD
    """
    pass  # (можно оставить пустым, если не используете)


def check_stagnant_trade_exit(symbol, trade_data):
    """
    Exit trades that haven't progressed after X minutes
    """
    pass  # (можно оставить пустым, если не используете)


def monitor_active_trades():
    """
    Periodically monitor open trades for micro-profit or timeout exit
    """
    while True:
        try:
            trades = trade_manager._trades.copy()
            for symbol, trade_data in trades.items():
                symbol = extract_symbol(symbol)

                check_micro_profit_exit(symbol, trade_data)
                check_stagnant_trade_exit(symbol, trade_data)
        except Exception as e:
            log(f"[Monitor Trades] Error: {e}", level="ERROR")

        time.sleep(30)


def handle_panic(stop_event):
    """
    Закрывает все позиции (panic).
    Закрывает ордера, позиции на бирже и чистит trade_manager,
    но НЕ делает os._exit(0), чтобы main.py смог корректно завершиться.
    """
    global open_positions_count, dry_run_positions_count
    with open_positions_lock:
        open_positions_count = 0
        dry_run_positions_count = 0

    max_retries = 3
    retry_delay = 5

    # Закрываем все сделки из trade_manager
    for symbol in list(trade_manager._trades.keys()):
        close_real_trade(symbol)

    # Проверяем и закрываем любые оставшиеся позиции/ордера напрямую через биржу
    for attempt in range(max_retries):
        try:
            positions = exchange.fetch_positions()
            if not positions:
                log("[Panic] No positions found on exchange.", level="INFO")
                break

            active_positions = [pos for pos in positions if float(pos.get("contracts", 0)) != 0]
            if not active_positions:
                log("[Panic] All positions closed.", level="INFO")
                break

            for pos in active_positions:
                sym = pos["symbol"]
                open_orders = exchange.fetch_open_orders(sym)
                for order in open_orders:
                    exchange.cancel_order(order["id"], sym)
                    log(f"[Panic] Cancelled order {order['id']} for {sym}", level="INFO")

                pos_after = exchange.fetch_positions([sym])[0]
                if float(pos_after.get("contracts", 0)) > 0:
                    qty = float(pos_after["contracts"])
                    side = "sell" if pos_after["side"] == "long" else "buy"
                    exchange.create_market_order(sym, side, qty)
                    log(f"[Panic] Force-closed position for {sym}: qty={qty}", level="INFO")

        except Exception as e:
            log(f"[Panic] attempt {attempt + 1}/{max_retries} error: {e}", level="ERROR")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                send_telegram_message(f"❌ Failed to close all positions in panic: {e}", force=True)

    # Очищаем локальные данные по сделкам и обновляем кэш
    trade_manager._trades.clear()
    initialize_cache()

    log("Panic close executed: All trades closed, counters reset", level="INFO")
    send_telegram_message("🚨 *Panic Close Executed*:\nAll positions closed.", force=True)

    # Ставим stop_event, чтобы бот завершил главный цикл естественно
    stop_event.set()
