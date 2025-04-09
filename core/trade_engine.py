# trade_engine.py
import threading
import time

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
    FLAT_ADJUSTMENT,
    MIN_NOTIONAL,
    SL_PERCENT,
    SOFT_EXIT_ENABLED,
    SOFT_EXIT_SHARE,
    SOFT_EXIT_THRESHOLD,
    TP1_PERCENT,
    TP1_SHARE,
    TP2_PERCENT,
    TP2_SHARE,
    TREND_ADJUSTMENT,
    exchange,
)
from core.aggressiveness_controller import get_aggressiveness_score
from telegram.telegram_utils import send_telegram_message
from tp_logger import log_trade_result
from utils_core import get_cached_positions, safe_call_retry
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
open_positions_lock = threading.Lock()


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
        ohlcv = safe_call_retry(
            exchange.fetch_ohlcv, symbol, timeframe="15m", limit=15, label=f"fetch_ohlcv {symbol}"
        )
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1]

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
    global open_positions_count
    with open_positions_lock:
        open_positions_count += 1

    ticker = safe_call_retry(exchange.fetch_ticker, symbol, label=f"enter_trade {symbol}")
    if not ticker:
        log(f"[ERROR] Failed to fetch ticker for {symbol}", level="ERROR")
        send_telegram_message(f"⚠️ Failed to fetch ticker for {symbol}", force=True)
        with open_positions_lock:
            open_positions_count -= 1
        return
    entry_price = ticker["last"]
    start_time = now()

    if is_reentry:
        if get_position_size(symbol) > 0:
            log(f"Skipping re-entry for {symbol}: position already open", level="WARNING")
            with open_positions_lock:
                open_positions_count -= 1
            return
        log(f"Re-entry triggered for {symbol} at {entry_price}", level="INFO")
        send_telegram_message(f"🔄 Re-entry {symbol} @ {entry_price}", force=True)

    if qty * entry_price < MIN_NOTIONAL:
        send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
        with open_positions_lock:
            open_positions_count -= 1
        return

    # Базовые значения TP/SL
    tp1_percent = TP1_PERCENT
    tp2_percent = TP2_PERCENT
    sl_percent = SL_PERCENT

    # Адаптация TP/SL по режиму
    if AUTO_TP_SL_ENABLED:
        regime = get_market_regime(symbol)
        if regime == "flat":
            tp1_percent *= FLAT_ADJUSTMENT
            tp2_percent *= FLAT_ADJUSTMENT if tp2_percent else None
            sl_percent *= FLAT_ADJUSTMENT
            log(f"Adjusted TP/SL for {symbol}: flat regime (x{FLAT_ADJUSTMENT})", level="INFO")
        elif regime == "trend":
            tp2_percent *= TREND_ADJUSTMENT if tp2_percent else None
            sl_percent *= TREND_ADJUSTMENT
            log(
                f"Adjusted TP/SL for {symbol}: trend regime (x{TREND_ADJUSTMENT} for TP2/SL)",
                level="INFO",
            )

    if score == 3:
        tp1_percent *= 0.8
        tp2_percent = None
        sl_percent *= 0.8
        log("🎯 TP/SL adjusted for score 3")

    qty_tp1 = round(qty * TP1_SHARE, 3)
    qty_tp2 = round(qty * TP2_SHARE, 3) if tp2_percent else 0

    tp1_price = (
        entry_price * (1 + tp1_percent) if side == "buy" else entry_price * (1 - tp1_percent)
    )
    tp2_price = (
        entry_price * (1 + tp2_percent)
        if side == "buy"
        else None
        if not tp2_percent
        else entry_price * (1 - tp2_percent)
    )
    sl_price = entry_price * (1 - sl_percent) if side == "buy" else entry_price * (1 + sl_percent)

    if DRY_RUN:
        log(
            f"[DRY] Entering {side.upper()} on {symbol} at {entry_price:.5f} (qty: {qty:.2f})",
            level="INFO",
        )
        msg = f"DRY-RUN {'REENTRY ' if is_reentry else ''}{side.upper()}{symbol}@{entry_price:.2f} Qty:{qty:.2f}"
        send_telegram_message(msg, force=True, parse_mode=None)
    else:
        safe_call_retry(
            exchange.create_limit_order,
            symbol,
            "sell" if side == "buy" else "buy",
            qty_tp1,
            tp1_price,
            label=f"create_limit_order TP1 {symbol}",
        )
        if tp2_price and qty_tp2 > 0:
            safe_call_retry(
                exchange.create_limit_order,
                symbol,
                "sell" if side == "buy" else "buy",
                qty_tp2,
                tp2_price,
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
            r"✅ NEW TRADE" + (" (Re-entry)" if is_reentry else "") + r"\n"
            r"Symbol: {symbol}\nSide: {side_upper}\nEntry: {entry_price}\n"
            r"Qty: {qty}\nTP1: +{tp1_percent}%"
            + (r" / TP2: +{tp2_percent}%" if tp2_price else "")
            + r"\nSL: -{sl_percent}%"
        ).format(
            symbol=symbol,
            side_upper=side.upper(),
            entry_price=round(entry_price, 4),
            qty=qty,
            tp1_percent=round(tp1_percent * 100, 1),
            tp2_percent=round(tp2_percent * 100, 1) if tp2_price else "",
            sl_percent=round(sl_percent * 100, 1),
        )
        send_telegram_message(msg, force=True)

    trade_data = {
        "symbol": symbol,
        "side": side,
        "entry": round(entry_price, 4),
        "qty": qty,
        "tp1": round(tp1_percent * 100, 1),
        "tp2": round(tp2_percent * 100, 1) if tp2_price else None,
        "sl": round(sl_percent * 100, 1),
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
            threading.Thread(
                target=run_break_even,
                args=(symbol, side, entry_price, tp1_percent),
                daemon=True,
            ).start()
        if SOFT_EXIT_ENABLED:
            threading.Thread(
                target=run_soft_exit,
                args=(symbol, side, entry_price, tp1_percent, qty),
                daemon=True,
            ).start()


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

    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
                "last"
            ]
            if (side == "buy" and price >= trigger) or (side == "sell" and price <= trigger):
                stop_price = round(entry_price, 4)
                safe_call_retry(
                    exchange.create_order,
                    symbol,
                    "STOP_MARKET",
                    "sell" if side == "buy" else "buy",
                    None,
                    params={"stopPrice": stop_price, "reduceOnly": True},
                    label=f"create_break_even {symbol}",
                )
                send_telegram_message(f"🔒 Break-even activated for {symbol}", force=True)
                trade_manager.update_trade(symbol, "tp1_hit", True)
                break
            time.sleep(check_interval)
        except Exception as e:
            print(f"[ERROR] Break-even error for {symbol}: {e}")
            break


def run_adaptive_trailing_stop(symbol, side, entry_price, check_interval=5):
    try:
        ohlcv = safe_call_retry(
            exchange.fetch_ohlcv, symbol, timeframe="15m", limit=15, label=f"fetch_ohlcv {symbol}"
        )
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        atr = max([h - low for h, low in zip(highs, lows)])
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1]
        multiplier = 3 if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD else 2
        if adx > 25:
            multiplier *= 0.7
        trailing_distance = atr * multiplier
        log(f"{symbol} 📐 ADX: {adx:.1f}, Trailing distance: {trailing_distance:.5f}")
    except Exception as e:
        log(f"[ERROR] Trailing init fallback: {e}")
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
            print(f"[ERROR] Adaptive trailing error for {symbol}: {e}")
            break


def run_soft_exit(symbol, side, entry_price, tp1_percent, qty, check_interval=5):
    tp1_price = (
        entry_price * (1 + tp1_percent) if side == "buy" else entry_price * (1 - tp1_percent)
    )
    soft_exit_price = (
        entry_price + (tp1_price - entry_price) * SOFT_EXIT_THRESHOLD
        if side == "buy"
        else entry_price - (entry_price - tp1_price) * SOFT_EXIT_THRESHOLD
    )
    soft_exit_qty = qty * SOFT_EXIT_SHARE

    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
                "last"
            ]
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
                break
            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Soft Exit error for {symbol}: {e}", level="ERROR")
            break


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    global open_positions_count
    with open_positions_lock:
        open_positions_count -= 1

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"⚠️ No trade info for {symbol} — cannot record result")
        return

    duration = int((time.time() - trade["start_time"].timestamp()) / 60)
    pnl = ((exit_price - entry_price) / entry_price) * 100
    if side == "sell":
        pnl *= -1

    log_trade_result(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        tp1_hit=trade.get("tp1_hit", False),
        tp2_hit=trade.get("tp2_hit", False),
        sl_hit=(result_type == "sl"),
        pnl_percent=round(pnl, 2),
        result="WIN" if pnl > 0 else "LOSS",
        duration_minutes=duration,
        htf_trend=trade.get("htf_trend", False),
    )

    msg = (
        f"📤 *Trade Closed* [{result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(pnl, 2)}% | Held: {duration} min"
    )
    send_telegram_message(msg, force=True)

    trade_manager.remove_trade(symbol)


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
        side = trade["side"]
        entry_price = trade["entry"]
        qty = trade["qty"]
        exit_price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")[
            "last"
        ]

        if side == "buy":
            safe_call_retry(
                exchange.create_market_sell_order, symbol, qty, label=f"close_sell {symbol}"
            )
        else:
            safe_call_retry(
                exchange.create_market_buy_order, symbol, qty, label=f"close_buy {symbol}"
            )

        record_trade_result(symbol, side, entry_price, exit_price, "smart_switch")
        log(f"[SmartSwitch] Closed {symbol} position at {exit_price}", level="INFO")
        trade_manager.set_last_closed_time(symbol, time.time())

    except Exception as e:
        log(f"[SmartSwitch] Error closing real trade {symbol}: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to close trade {symbol}: {str(e)}", force=True)
