# trade_engine.py
import os
import threading
import time
import traceback
from threading import Lock
from telegram.telegram_utils import escape_markdown_v2


import pandas as pd
import ta

from config import (
    ADX_FLAT_THRESHOLD,
    ADX_TREND_THRESHOLD,
    AGGRESSIVENESS_THRESHOLD,
    AUTO_TP_SL_ENABLED,
    BREAKEVEN_TRIGGER,
    DRY_RUN,
    ENABLE_BREAKEVEN,
    ENABLE_TRAILING,
    MAX_MARGIN_PERCENT,
    MAX_OPEN_ORDERS,
    MAX_POSITIONS,
    MIN_NOTIONAL_OPEN,
    MIN_NOTIONAL_ORDER,
    SL_PERCENT,
    SOFT_EXIT_ENABLED,
    SOFT_EXIT_SHARE,
    SOFT_EXIT_THRESHOLD,
    TAKER_FEE_RATE,
    TP1_PERCENT,
    TP2_PERCENT,
    USE_TESTNET,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.binance_api import fetch_ohlcv
from core.exchange_init import exchange
from core.tp_utils import calculate_tp_levels
from telegram.telegram_utils import send_telegram_message
from tp_logger import log_trade_result
from utils_core import (
    get_cached_balance,
    get_cached_positions,
    initialize_cache,
    load_state,
    safe_call_retry,
)
from utils_logging import log, now


class TradeInfoManager:
    def __init__(self):
        self._trades = {}
        self._lock = threading.Lock()

    def add_trade(self, symbol, trade_data):
        with self._lock:
            self._trades[symbol] = trade_data

    def get_trade(self, symbol):
        with self._lock:
            return self._trades.get(symbol)

    def update_trade(self, symbol, key, value):
        with self._lock:
            if symbol in self._trades:
                self._trades[symbol][key] = value

    def remove_trade(self, symbol):
        with self._lock:
            return self._trades.pop(symbol, None)

    def get_last_score(self, symbol):
        with self._lock:
            return self._trades.get(symbol, {}).get("score", 0)

    def get_last_closed_time(self, symbol):
        with self._lock:
            return self._trades.get(symbol, {}).get("last_closed_time", None)

    def set_last_closed_time(self, symbol, timestamp):
        with self._lock:
            if symbol not in self._trades:
                self._trades[symbol] = {}
            self._trades[symbol]["last_closed_time"] = timestamp


trade_manager = TradeInfoManager()
monitored_stops = {}
monitored_stops_lock = threading.Lock()
open_positions_count = 0
dry_run_positions_count = 0
open_positions_lock = threading.Lock()
logged_trades = set()
logged_trades_lock = Lock()


def calculate_risk_amount(balance, risk_percent):
    return balance * risk_percent


def calculate_position_size(entry_price, stop_price, risk_amount):
    risk_per_unit = abs(entry_price - stop_price)
    return round(risk_amount / risk_per_unit, 3) if risk_per_unit > 0 else 0


def get_position_size(symbol):
    try:
        positions = get_cached_positions()
        for pos in positions:
            if pos["symbol"] == symbol and float(pos["contracts"]) > 0:
                return float(pos["contracts"])
    except Exception as e:
        log(f"Error in get_position_size for {symbol}: {e}", level="ERROR")
    return 0


def get_market_regime(symbol):
    try:
        ohlcv = fetch_ohlcv(symbol, timeframe="15m", limit=50)
        log(f"{symbol} 🔍 Fetched {len(ohlcv)} candles for timeframe 15m", level="DEBUG")
        if not ohlcv or len(ohlcv) < 28:
            log(
                f"{symbol} ⚠️ Insufficient data: only {len(ohlcv) if ohlcv else 0} candles available, need at least 28 for ADX",
                level="WARNING",
            )
            return "neutral"

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if len(adx_series) < 1 or adx_series.isna().all():
            log(
                f"{symbol} ⚠️ ADX calculation failed: insufficient data after processing",
                level="WARNING",
            )
            return "neutral"
        adx = adx_series.iloc[-1]

        log(f"{symbol} 🔍 Market regime: ADX = {adx:.2f}", level="DEBUG")
        if adx > ADX_TREND_THRESHOLD:
            log(
                f"{symbol} 🔍 Market regime determined: trend (ADX > {ADX_TREND_THRESHOLD})",
                level="INFO",
            )
            return "trend"
        elif adx < ADX_FLAT_THRESHOLD:
            log(
                f"{symbol} 🔍 Market regime determined: flat (ADX < {ADX_FLAT_THRESHOLD})",
                level="INFO",
            )
            return "flat"
        else:
            log(
                f"{symbol} 🔍 Market regime determined: neutral (ADX between {ADX_FLAT_THRESHOLD} and {ADX_TREND_THRESHOLD})",
                level="INFO",
            )
            return "neutral"
    except Exception as e:
        log(f"[ERROR] Failed to determine market regime for {symbol}: {e}", level="ERROR")
        return "neutral"


def enter_trade(symbol, side, qty, score=5, is_reentry=False):
    state = load_state()
    if state.get("stopping"):
        log("Cannot enter trade: bot is stopping.", level="WARNING")
        return

    if len(trade_manager._trades) >= MAX_POSITIONS:
        log(f"[Skip] Trade limit reached ({MAX_POSITIONS})", level="INFO")
        return

    try:
        positions = exchange.fetch_positions()
        active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
        if active_positions >= MAX_POSITIONS:
            log(
                f"[Skipping {symbol}] Max open positions ({MAX_POSITIONS}) reached. Active: {active_positions}",
                level="INFO",
            )
            return
    except Exception as e:
        log(f"[Enter Trade] Failed to fetch positions for {symbol}: {e}", level="ERROR")
        return

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

        from config import LEVERAGE_MAP

        leverage_key = (
            symbol.split(":")[0].replace("/", "") if USE_TESTNET else symbol.replace("/", "")
        )
        leverage = LEVERAGE_MAP.get(leverage_key, 1)
        adjusted_qty = qty * leverage

        notional = adjusted_qty * entry_price
        while notional < MIN_NOTIONAL_OPEN:
            adjusted_qty *= 1.1
            notional = adjusted_qty * entry_price
            log(
                f"[Enter Trade] Adjusted qty for {symbol} to {adjusted_qty:.6f} to meet notional {notional:.2f}",
                level="DEBUG",
            )

        if notional < MIN_NOTIONAL_OPEN:
            log(
                f"{symbol} ⚠️ Notional too small: {notional:.2f} < {MIN_NOTIONAL_OPEN}",
                level="WARNING",
            )
            send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
            return

        balance = get_cached_balance()
        max_margin = balance * MAX_MARGIN_PERCENT
        required_margin = notional / leverage
        if required_margin > max_margin * 0.9:  # Буфер 90%
            adjusted_qty = (max_margin * leverage * 0.9) / entry_price
            notional = adjusted_qty * entry_price
            log(
                f"[Enter Trade] Adjusted qty for {symbol} to {adjusted_qty:.6f} to meet max margin limit (required: {required_margin:.2f}, max: {max_margin:.2f})",
                level="DEBUG",
            )

        precision = exchange.markets[symbol]["precision"]["amount"]
        min_qty = exchange.markets[symbol]["limits"]["amount"]["min"]
        adjusted_qty = round(adjusted_qty, precision)
        if adjusted_qty < min_qty:
            adjusted_qty = max(min_qty, adjusted_qty)
            notional = adjusted_qty * entry_price
            log(
                f"[Enter Trade] Adjusted qty for {symbol} to {adjusted_qty:.6f} to meet minimum qty {min_qty}",
                level="DEBUG",
            )
        elif adjusted_qty == 0:
            adjusted_qty = 10**-precision
            notional = adjusted_qty * entry_price
            log(
                f"[Enter Trade] Adjusted qty for {symbol} to {adjusted_qty:.6f} to meet minimum precision {precision}",
                level="DEBUG",
            )

        if notional < MIN_NOTIONAL_OPEN:
            log(
                f"{symbol} ⚠️ Notional too small after adjustment: {notional:.2f} < {MIN_NOTIONAL_OPEN}",
                level="WARNING",
            )
            send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
            return
        qty = adjusted_qty

        open_orders = exchange.fetch_open_orders(symbol)
        if len(open_orders) >= MAX_OPEN_ORDERS:
            log(
                f"[TP/SL] Skipping TP/SL for {symbol} — max open orders ({MAX_OPEN_ORDERS}) reached",
                level="DEBUG",
            )
            return

        if not DRY_RUN:
            try:
                if side.lower() == "sell":
                    exchange.create_market_sell_order(symbol, qty)
                else:
                    exchange.create_market_buy_order(symbol, qty)
                log(
                    f"[Enter Trade] Opened {side.upper()} position for {symbol}: qty={qty}, entry={entry_price}",
                    level="INFO",
                )
            except Exception as e:
                log(f"[Enter Trade] Failed to open position for {symbol}: {str(e)}", level="ERROR")
                send_telegram_message(f"❌ Failed to open trade {symbol}: {str(e)}", force=True)
                return

        regime = get_market_regime(symbol) if AUTO_TP_SL_ENABLED else None
        tp1_price, tp2_price, sl_price, qty_tp1_share, qty_tp2_share = calculate_tp_levels(
            entry_price, side, regime, score
        )

        # Проверка на None
        if any(v is None for v in [entry_price, tp1_price, sl_price]):
            log(
                f"⚠️ Skipping TP/SL for {symbol} — invalid prices (entry={entry_price}, tp1={tp1_price}, sl={sl_price})",
                level="ERROR",
            )
            send_telegram_message(f"⚠️ Invalid prices for {symbol}", force=True)
            return

        qty_tp1 = round(qty * qty_tp1_share, precision)
        qty_tp2 = round(qty * qty_tp2_share, precision)

        if qty_tp1 * tp1_price < MIN_NOTIONAL_ORDER:
            log(
                f"[Enter Trade] TP1 notional too small for {symbol}: {qty_tp1 * tp1_price:.2f} < {MIN_NOTIONAL_ORDER}",
                level="WARNING",
            )
            qty_tp1 = 0
        if tp2_price and qty_tp2 * tp2_price < MIN_NOTIONAL_ORDER:
            log(
                f"[Enter Trade] TP2 notional too small for {symbol}: {qty_tp2 * tp2_price:.2f} < {MIN_NOTIONAL_ORDER}",
                level="WARNING",
            )
            qty_tp2 = 0

        gross_profit_tp1 = qty_tp1 * abs(tp1_price - entry_price)
        commission = 2 * (qty * entry_price * TAKER_FEE_RATE)
        net_profit_tp1 = gross_profit_tp1 - commission
        log(
            f"{symbol} Net profit on TP1: {net_profit_tp1:.2f} USD, Commission: {commission:.2f} USD",
            level="DEBUG",
        )

        if DRY_RUN:
            log(
                f"[DRY] Entering {side.upper()} on {symbol} at {entry_price:.5f} (qty: {qty:.2f})",
                level="INFO",
            )
            msg = f"DRY-RUN {'REENTRY ' if is_reentry else ''}{side.upper()}{symbol}@{entry_price:.2f} Qty:{qty:.3f}"
            send_telegram_message(msg, force=True, parse_mode=None)
        else:
            if qty_tp1 > 0:
                safe_call_retry(
                    exchange.create_limit_order,
                    symbol,
                    "sell" if side == "buy" else "buy",
                    qty_tp1,
                    tp1_price,
                    params={"reduceOnly": True},
                    label=f"create_limit_order TP1 {symbol}",
                )
            if tp2_price and qty_tp2 > 0:
                safe_call_retry(
                    exchange.create_limit_order,
                    symbol,
                    "sell" if side == "buy" else "buy",
                    qty_tp2,
                    tp2_price,
                    params={"reduceOnly": True},
                    label=f"create_limit_order TP2 {symbol}",
                )
            safe_call_retry(
                exchange.create_order,
                symbol,
                "STOP_MARKET",
                "sell" if side == "buy" else "buy",
                qty,
                params={"stopPrice": round(sl_price, 4), "reduceOnly": True},
                label=f"create_stop_order {symbol}",
            )
            msg = (
            "🚀 *NEW TRADE OPENED*{}\n"
            "📊 *Symbol:* `{}`\n"
            "🧭 *Side:* `{}`\n"
            "🎯 *Entry:* `{}`\n"
            "📦 *Qty:* `{}`\n"
            "🏁 *TP1:* `+{}%`{}\n"
            "🛑 *SL:* `-{}%`"
        ).format(
            " (Re-entry)" if is_reentry else "",
            escape_markdown_v2(symbol),
            escape_markdown_v2(side.upper()),
            round(entry_price, 4),
            qty,
            round(TP1_PERCENT * 100, 1),
            f" / TP2: `+{round(TP2_PERCENT * 100, 1)}%`" if tp2_price and qty_tp2 > 0 else "",
            round(SL_PERCENT * 100, 1),
        )
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

        trade_data = {
            "symbol": symbol,
            "side": side,
            "entry": round(entry_price, 4),
            "qty": qty,
            "tp1": round(TP1_PERCENT * 100, 1),
            "tp2": round(TP2_PERCENT * 100, 1) if tp2_price else None,
            "sl": round(SL_PERCENT * 100, 1),
            "start_time": start_time,
            "tp1_hit": False,
            "tp2_hit": False,
            "score": score,
            "soft_exit_hit": False,
        }
        trade_manager.add_trade(symbol, trade_data)

        if not DRY_RUN:
            track_stop_loss(symbol, side, entry_price, qty, start_time)
            if ENABLE_TRAILING:
                threading.Thread(
                    target=run_adaptive_trailing_stop,
                    args=(symbol, side, entry_price),
                    daemon=True,
                ).start()
            if ENABLE_BREAKEVEN:
                log(f"[DEBUG] Starting break-even thread for {symbol}", level="DEBUG")
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

        initialize_cache()

    except Exception as e:
        log(f"[Enter Trade] Unexpected error for {symbol}: {str(e)}", level="ERROR")
        send_telegram_message(f"❌ Unexpected error in trade {symbol}: {str(e)}", force=True)
    finally:
        with open_positions_lock:
            if DRY_RUN:
                dry_run_positions_count -= 1
            else:
                open_positions_count -= 1


# Остальные функции без изменений
def track_stop_loss(symbol, side, entry_price, qty, opened_at):
    with monitored_stops_lock:
        monitored_stops[symbol] = {
            "side": side,
            "entry": entry_price,
            "qty": qty,
            "opened_at": opened_at,
        }


def run_break_even(symbol, side, entry_price, tp_percent, check_interval=5):
    target = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    trigger = (
        entry_price + (target - entry_price) * BREAKEVEN_TRIGGER
        if side == "buy"
        else entry_price - (entry_price - target) * BREAKEVEN_TRIGGER
    )
    log(
        f"[DEBUG] Break-even for {symbol}: entry={entry_price}, target={target}, trigger={trigger}",
        level="DEBUG",
    )

    while True:
        try:
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(
                    f"[Break-Even] Trade for {symbol} no longer exists, stopping break-even thread",
                    level="INFO",
                )
                break

            position = get_position_size(symbol)
            if position <= 0:
                log(
                    f"[Break-Even] Position for {symbol} closed, stopping break-even thread",
                    level="INFO",
                )
                break

            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
                "last"
            ]
            log(
                f"[DEBUG] Break-even check for {symbol}: current price={price}, trigger={trigger}",
                level="DEBUG",
            )
            if (side == "buy" and price >= trigger) or (side == "sell" and price <= trigger):
                stop_price = float(entry_price)
                precision = exchange.markets[symbol]["precision"]["price"]
                stop_price = round(stop_price, precision)

                qty = trade.get("qty", 0)
                qty = float(qty)
                qty_precision = exchange.markets[symbol]["precision"]["amount"]
                qty = round(qty, qty_precision)

                log(
                    f"[DEBUG] Creating break-even for {symbol} with stop_price: {stop_price}, qty: {qty}",
                    level="DEBUG",
                )
                safe_call_retry(
                    exchange.create_order,
                    symbol,
                    "STOP_MARKET",
                    "sell" if side == "buy" else "buy",
                    qty,
                    params={"stopPrice": stop_price, "reduceOnly": True},
                    label=f"create_break_even {symbol}",
                )
                send_telegram_message(f"🔒 Break-even activated for {symbol}", force=True)
                trade_manager.update_trade(symbol, "tp1_hit", True)

                while True:
                    position = get_position_size(symbol)
                    if position <= 0:
                        trade_manager.remove_trade(symbol)
                        log(
                            f"[Break-Even] Position for {symbol} closed, removed from trade_manager",
                            level="INFO",
                        )
                        break
                    time.sleep(check_interval)
                break
        except Exception as e:
            log(f"[ERROR] Break-even error for {symbol}: {e}", level="ERROR")
            break


def run_adaptive_trailing_stop(symbol, side, entry_price, check_interval=5):
    try:
        timeframe = "15m"
        limit = 50
        ohlcv = fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv or len(ohlcv) < 28:
            log(
                f"[WARNING] Insufficient data for trailing stop for {symbol}: {len(ohlcv)} candles, need at least 28",
                level="WARNING",
            )
            trailing_distance = entry_price * 0.02
        else:
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            closes = [c[4] for c in ohlcv]
            df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
            atr = max([h - low for h, low in zip(highs, lows)])
            adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
            if len(adx_series) < 1 or adx_series.isna().all():
                log(
                    f"[WARNING] ADX calculation failed for {symbol}: insufficient data after processing",
                    level="WARNING",
                )
                trailing_distance = entry_price * 0.02
            else:
                adx = adx_series.iloc[-1]
                multiplier = 3 if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD else 2
                if adx > 25:
                    multiplier *= 0.7
                trailing_distance = atr * multiplier
                log(f"{symbol} 📐 ADX: {adx:.1f}, Trailing distance: {trailing_distance:.5f}")
    except Exception as e:
        log(f"[ERROR] Trailing init fallback: {e}", level="ERROR")
        trailing_distance = entry_price * 0.02

    highest = entry_price
    lowest = entry_price

    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
                "last"
            ]
            if side == "buy":
                if price > highest:
                    highest = price
                if price <= highest - trailing_distance:
                    size = get_position_size(symbol)
                    safe_call_retry(
                        exchange.create_market_sell_order,
                        symbol,
                        size,
                        label=f"trailing_sell {symbol}",
                    )
                    send_telegram_message(
                        f"📉 Trailing stop hit (LONG) {symbol} @ {price}", force=True
                    )
                    record_trade_result(symbol, side, entry_price, price, "trailing")
                    break
            else:
                if price < lowest:
                    lowest = price
                if price >= lowest + trailing_distance:
                    size = get_position_size(symbol)
                    safe_call_retry(
                        exchange.create_market_buy_order,
                        symbol,
                        size,
                        label=f"trailing_buy {symbol}",
                    )
                    send_telegram_message(
                        f"📈 Trailing stop hit (SHORT) {symbol} @ {price}", force=True
                    )
                    record_trade_result(symbol, side, entry_price, price, "trailing")
                    break
            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Adaptive trailing error for {symbol}: {e}", level="ERROR")
            break


def run_soft_exit(symbol, side, entry_price, tp1_percent, qty, check_interval=5):
    global open_positions_count, dry_run_positions_count
    tp1_price = (
        entry_price * (1 + tp1_percent) if side == "buy" else entry_price * (1 - tp1_percent)
    )
    soft_exit_price = (
        entry_price + (tp1_price - entry_price) * SOFT_EXIT_THRESHOLD
        if side == "buy"
        else entry_price - (entry_price - tp1_price) * SOFT_EXIT_THRESHOLD
    )
    soft_exit_qty = qty * SOFT_EXIT_SHARE

    log(
        f"[Soft Exit] Monitoring {symbol}: entry={entry_price}, tp1_price={tp1_price}, "
        f"soft_exit_price={soft_exit_price}, soft_exit_qty={soft_exit_qty}",
        level="DEBUG",
    )

    trade_closed = False
    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
                "last"
            ]
            log(
                f"[Soft Exit] Checking {symbol}: current price={price}, soft_exit_price={soft_exit_price}",
                level="DEBUG",
            )

            if (side == "buy" and price >= soft_exit_price) or (
                side == "sell" and price <= soft_exit_price
            ):
                if DRY_RUN:
                    log(
                        f"[DRY] Soft Exit triggered for {symbol} at {price}: closing {soft_exit_qty}",
                        level="INFO",
                    )
                    send_telegram_message(f"🔄 [DRY] Soft Exit {symbol} @ {price}", force=True)
                else:
                    safe_call_retry(
                        exchange.create_market_order,
                        symbol,
                        "sell" if side == "buy" else "buy",
                        soft_exit_qty,
                        label=f"soft_exit {symbol}",
                    )
                    send_telegram_message(f"🔄 Soft Exit {symbol} @ {price}", force=True)
                    trade_manager.update_trade(symbol, "soft_exit_hit", True)
                    log(f"[Soft Exit] Soft exit executed for {symbol} at {price}", level="INFO")

                    if not trade_closed:
                        record_trade_result(symbol, side, entry_price, price, "soft_exit")
                        trade_closed = True

                    try:
                        open_orders = exchange.fetch_open_orders(symbol)
                        for order in open_orders:
                            exchange.cancel_order(order["id"], symbol)
                            log(
                                f"[Soft Exit] Cancelled order {order['id']} for {symbol}",
                                level="INFO",
                            )
                    except Exception as e:
                        log(f"[Soft Exit] Failed to cancel orders for {symbol}: {e}", level="ERROR")
                        send_telegram_message(
                            f"❌ Failed to cancel orders for {symbol}: {e}", force=True
                        )

                    position = get_position_size(symbol)
                    log(
                        f"[Soft Exit] Remaining position size for {symbol}: {position}",
                        level="DEBUG",
                    )
                    if position <= 0:
                        trade_manager.remove_trade(symbol)
                        log(
                            f"[Soft Exit] Fully closed {symbol}, removed from trade_manager",
                            level="INFO",
                        )
                        initialize_cache()
                        break

            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Soft Exit error for {symbol}: {e}", level="ERROR")
            break


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    global open_positions_count, dry_run_positions_count

    caller_stack = traceback.format_stack()[-2]
    log(
        f"[DEBUG] record_trade_result called for {symbol}, result_type={result_type}, caller: {caller_stack}",
        level="DEBUG",
    )

    trade_key = f"{symbol}_{result_type}_{entry_price}_{round(exit_price, 4)}"
    with logged_trades_lock:
        if trade_key in logged_trades:
            log(
                f"[DEBUG] Skipping duplicate logging for {symbol}, result_type={result_type}",
                level="DEBUG",
            )
            return
        logged_trades.add(trade_key)

    with open_positions_lock:
        if DRY_RUN:
            dry_run_positions_count -= 1
        else:
            open_positions_count -= 1

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"⚠️ No trade info for {symbol} — cannot record result")
        return

    final_result_type = result_type
    if trade.get("soft_exit_hit", False) and result_type in ["manual", "stop"]:
        final_result_type = "soft_exit"

    duration = int((time.time() - trade["start_time"].timestamp()) / 60)
    pnl = ((exit_price - entry_price) / entry_price) * 100
    if side == "sell":
        pnl *= -1

    log(
        f"[DEBUG] Logging trade result for {symbol}: entry={entry_price}, exit={exit_price}, pnl={pnl:.2f}%",
        level="DEBUG",
    )

    log_trade_result(
        symbol=symbol,
        direction=side.upper(),
        entry_price=entry_price,
        exit_price=exit_price,
        qty=trade["qty"],
        tp1_hit=trade.get("tp1_hit", False),
        tp2_hit=trade.get("tp2_hit", False),
        sl_hit=(result_type == "sl"),
        pnl_percent=round(pnl, 2),
        duration_minutes=duration,
        htf_confirmed=False,
        atr=0.0,
        adx=0.0,
        bb_width=0.0,
        result_type=final_result_type,
    )

    msg = (
        f"📤 *Trade Closed* [{final_result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(pnl, 2)}% | Held: {duration} min"
    )
    send_telegram_message(msg, force=True)

    trade_manager.remove_trade(symbol)
    log(f"[DEBUG] Trade {symbol} removed from trade_manager after logging", level="DEBUG")


def close_dry_trade(symbol):
    trade = trade_manager.get_trade(symbol)
    if DRY_RUN and trade:
        exit_price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
            "last"
        ]
        record_trade_result(symbol, trade["side"], trade["entry"], exit_price, "manual")
        log(f"[DRY] Closed {symbol} at {exit_price}", level="INFO")
        send_telegram_message(f"DRY RUN: Closed {symbol} at {exit_price}", force=True)
        trade_manager.set_last_closed_time(symbol, time.time())


def close_real_trade(symbol):
    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"[SmartSwitch] No active trade found for {symbol}", level="WARNING")
        return

    try:
        positions = exchange.fetch_positions()
        position = next(
            (p for p in positions if p["symbol"] == symbol and float(p.get("contracts", 0)) > 0),
            None,
        )
        if not position:
            log(f"[SmartSwitch] No open position found for {symbol} on exchange", level="WARNING")
        else:
            side = trade["side"]
            qty = float(position["contracts"])
            ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")
            exit_price = ticker["last"]

            if not DRY_RUN:
                if side == "buy":
                    safe_call_retry(
                        exchange.create_market_sell_order, symbol, qty, label=f"close_sell {symbol}"
                    )
                else:
                    safe_call_retry(
                        exchange.create_market_buy_order, symbol, qty, label=f"close_buy {symbol}"
                    )

            entry_price = trade["entry"]
            pnl_percent = (
                ((exit_price - entry_price) / entry_price * 100)
                if side == "buy"
                else ((entry_price - exit_price) / entry_price * 100)
            )
            duration = int((time.time() - trade["start_time"].timestamp()) / 60)

            log_trade_result(
                symbol=symbol,
                direction=side.upper(),
                entry_price=entry_price,
                exit_price=exit_price,
                qty=qty,
                tp1_hit=trade.get("tp1_hit", False),
                tp2_hit=trade.get("tp2_hit", False),
                sl_hit=False,
                pnl_percent=pnl_percent,
                duration_minutes=duration,
                htf_confirmed=False,
                atr=0.0,
                adx=0.0,
                bb_width=0.0,
            )
            log(f"[SmartSwitch] Closed {symbol} position at {exit_price}", level="INFO")

        open_orders = exchange.fetch_open_orders(symbol)
        for order in open_orders:
            try:
                exchange.cancel_order(order["id"], symbol)
                log(f"[Close Trade] Cancelled order {order['id']} for {symbol}", level="INFO")
            except Exception as e:
                log(
                    f"[Close Trade] Failed to cancel order {order['id']} for {symbol}: {e}",
                    level="ERROR",
                )
                send_telegram_message(
                    f"❌ Failed to cancel order for {symbol}: {str(e)}", force=True
                )

        trade_manager.remove_trade(symbol)
        trade_manager.set_last_closed_time(symbol, time.time())
        initialize_cache()

    except Exception as e:
        log(f"[SmartSwitch] Error closing real trade {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trade {symbol}: {str(e)}", force=True)


def open_real_trade(symbol, direction, qty, entry_price):
    try:
        side = "buy" if direction.lower() == "buy" else "sell"
        order = exchange.create_market_order(symbol, side, qty)
        log(
            f"[Open Trade] Opened {direction} position for {symbol}: qty={qty}, entry={entry_price}",
            level="INFO",
        )

        initialize_cache()
        return order
    except Exception as e:
        log(f"[Open Trade] Failed for {symbol}: {e}", level="ERROR")
        raise


def handle_panic(stop_event):
    global open_positions_count, dry_run_positions_count
    with open_positions_lock:
        open_positions_count = 0
        dry_run_positions_count = 0

    max_retries = 3
    retry_delay = 5

    for symbol in list(trade_manager._trades.keys()):
        close_real_trade(symbol)

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
                symbol = pos["symbol"]
                open_orders = exchange.fetch_open_orders(symbol)
                for order in open_orders:
                    exchange.cancel_order(order["id"], symbol)
                    log(f"[Panic] Cancelled order {order['id']} for {symbol}", level="INFO")
                pos_after = exchange.fetch_positions([symbol])[0]
                if float(pos_after.get("contracts", 0)) > 0:
                    qty = float(pos_after["contracts"])
                    side = "sell" if pos_after["side"] == "long" else "buy"
                    exchange.create_market_order(symbol, side, qty)
                    log(f"[Panic] Force-closed position for {symbol}: qty={qty}", level="INFO")
        except Exception as e:
            log(
                f"[Panic] Failed to process positions (attempt {attempt + 1}/{max_retries}): {e}",
                level="ERROR",
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                send_telegram_message(
                    f"❌ Failed to close all positions during panic: {e}", force=True
                )

    trade_manager._trades.clear()
    initialize_cache()
    log("Panic close executed: All trades closed, counters reset", level="INFO")
    send_telegram_message("🚨 *Panic Close Executed*:\nAll positions closed.", force=True)

    stop_event.set()
    os._exit(0)
