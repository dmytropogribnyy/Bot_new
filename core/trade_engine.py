import threading
import time

import pandas as pd
import ta

from config import (
    BREAKEVEN_TRIGGER,
    DRY_RUN,
    ENABLE_BREAKEVEN,
    ENABLE_TRAILING,
    MIN_NOTIONAL,
    SL_PERCENT,
    TP1_PERCENT,
    TP1_SHARE,
    TP2_PERCENT,
    TP2_SHARE,
    exchange,
    is_aggressive,
)
from telegram.telegram_utils import send_telegram_message
from tp_logger import log_trade_result
from utils_core import get_cached_positions
from utils_logging import log, now

last_trade_info = {}
monitored_stops = {}


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


def enter_trade(symbol, side, qty, score=5):
    entry_price = exchange.fetch_ticker(symbol)["last"]
    start_time = now()

    if qty * entry_price < MIN_NOTIONAL:
        send_telegram_message(f"⚠️ Skipping {symbol}: notional too small", force=True)
        return

    tp1_percent = TP1_PERCENT
    tp2_percent = TP2_PERCENT
    sl_percent = SL_PERCENT

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
        msg = f"DRY RUN: {side.upper()} {symbol} at {entry_price:.5f} (qty: {qty:.2f})"
        send_telegram_message(msg, force=True)
    else:
        exchange.create_limit_order(symbol, "sell" if side == "buy" else "buy", qty_tp1, tp1_price)
        if tp2_price and qty_tp2 > 0:
            exchange.create_limit_order(
                symbol, "sell" if side == "buy" else "buy", qty_tp2, tp2_price
            )
        exchange.create_order(
            symbol,
            type="STOP_MARKET",
            side="sell" if side == "buy" else "buy",
            amount=qty,
            params={"stopPrice": round(sl_price, 4), "reduceOnly": True},
        )
        msg = (
            f"✅ NEW TRADE\n"
            f"Symbol: {symbol}\nSide: {side.upper()}\nEntry: {round(entry_price, 4)}\n"
            f"Qty: {qty}\nTP1: +{round(tp1_percent * 100, 1)}%"
            + (f" / TP2: +{round(tp2_percent * 100, 1)}%" if tp2_price else "")
            + f"\nSL: -{round(sl_percent * 100, 1)}%"
        )
        send_telegram_message(msg, force=True)

    last_trade_info[symbol] = {
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
    }

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


def track_stop_loss(symbol, side, entry_price, qty, opened_at):
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
            price = exchange.fetch_ticker(symbol)["last"]
            if (side == "buy" and price >= trigger) or (side == "sell" and price <= trigger):
                stop_price = round(entry_price, 4)
                exchange.create_order(
                    symbol,
                    "STOP_MARKET",
                    "sell" if side == "buy" else "buy",
                    None,
                    None,
                    {"stopPrice": stop_price, "reduceOnly": True},
                )
                send_telegram_message(f"🔒 Break-even activated for {symbol}", force=True)
                break
            time.sleep(check_interval)
        except Exception as e:
            print(f"[ERROR] Break-even error for {symbol}: {e}")
            break


def run_adaptive_trailing_stop(symbol, side, entry_price, check_interval=5):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe="15m", limit=15)
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        atr = max([h - low for h, low in zip(highs, lows)])
        df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
        adx = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx().iloc[-1]
        multiplier = 3 if is_aggressive else 2
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
            price = exchange.fetch_ticker(symbol)["last"]
            if side == "buy":
                if price > highest:
                    highest = price
                if price <= highest - trailing_distance:
                    size = get_position_size(symbol)
                    exchange.create_market_sell_order(symbol, size)
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
                    exchange.create_market_buy_order(symbol, size)
                    send_telegram_message(
                        f"📈 Trailing stop hit (SHORT) {symbol} @ {price}", force=True
                    )
                    record_trade_result(symbol, side, entry_price, price, "trailing")
                    break
            time.sleep(check_interval)
        except Exception as e:
            print(f"[ERROR] Adaptive trailing error for {symbol}: {e}")
            break


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    global last_trade_info
    trade = last_trade_info.get(symbol)
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
    )

    msg = (
        f"📤 *Trade Closed* [{result_type.upper()}]\n"
        f"• {symbol} — {side.upper()}\n"
        f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
        f"• PnL: {round(pnl, 2)}% | Held: {duration} min"
    )
    send_telegram_message(msg, force=True)

    if symbol in last_trade_info:
        del last_trade_info[symbol]


def close_dry_trade(symbol):
    """Закрытие симулированной позиции в DRY_RUN."""
    if DRY_RUN and symbol in last_trade_info:
        trade = last_trade_info[symbol]
        exit_price = exchange.fetch_ticker(symbol)["last"]
        record_trade_result(symbol, trade["side"], trade["entry"], exit_price, "manual")
        log(f"[DRY] Closed {symbol} at {exit_price}", level="INFO")
        send_telegram_message(f"DRY RUN: Closed {symbol} at {exit_price}", force=True)
