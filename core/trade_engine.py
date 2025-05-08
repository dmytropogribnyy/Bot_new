# trade_engine.py
import os
import threading
import time
import traceback
from datetime import datetime
from threading import Lock

import pandas as pd
import pytz
import ta

from common.config_loader import (
    ADX_FLAT_THRESHOLD,
    ADX_TREND_THRESHOLD,
    AGGRESSIVENESS_THRESHOLD,
    AUTO_CLOSE_PROFIT_THRESHOLD,  # Added import
    AUTO_TP_SL_ENABLED,
    BONUS_PROFIT_THRESHOLD,  # Added import
    BREAKEVEN_TRIGGER,
    BREAKOUT_DETECTION,
    DRY_RUN,
    ENABLE_BREAKEVEN,
    ENABLE_TRAILING,
    HIGH_ACTIVITY_HOURS,
    LEVERAGE_MAP,
    MAX_MARGIN_PERCENT,
    MAX_OPEN_ORDERS,
    MAX_POSITIONS,
    MICRO_PROFIT_ENABLED,
    MICRO_PROFIT_THRESHOLD,
    MICRO_TRADE_SIZE_THRESHOLD,
    MICRO_TRADE_TIMEOUT_MINUTES,
    MIN_NOTIONAL_OPEN,
    MIN_NOTIONAL_ORDER,
    PRIORITY_SMALL_BALANCE_PAIRS,
    SHORT_TERM_MODE,
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


# New functions for safe trade closing
def safe_close_trade(binance_client, symbol, trade_data):
    """
    Safely close a trade by cancelling all orders and closing the position.
    This ensures clean exits without lingering orders.
    """
    try:
        side = trade_data["side"]
        quantity = trade_data["quantity"]

        close_trade_and_cancel_orders(binance_client=binance_client, symbol=symbol, side=side, quantity=quantity)

        trade_manager._trades.pop(symbol, None)
        log(f"✅ Safe close complete for {symbol}. Position and orders cleared.", level="INFO")
    except Exception as e:
        log(f"❌ Error during safe close for {symbol}: {str(e)}", level="ERROR")


def close_trade_and_cancel_orders(binance_client, symbol, side, quantity, reduce_only=True):
    """
    Close a position with a market order and cancel all related orders.

    Args:
        binance_client: Binance client instance
        symbol: Trading pair symbol
        side: Position side (BUY/SELL)
        quantity: Position size
        reduce_only: Whether to use reduce_only parameter
    """
    try:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"

        # First cancel all orders to avoid conflicts
        try:
            binance_client.futures_cancel_all_open_orders(symbol=symbol.replace("/", ""))
            log(f"✅ Canceled all open orders for {symbol}.", level="INFO")
        except Exception as e:
            log(f"❌ Error canceling orders for {symbol}: {str(e)}", level="WARNING")

        # Then close the position
        order = binance_client.futures_create_order(symbol=symbol.replace("/", ""), side=close_side, type="MARKET", quantity=quantity, reduceOnly=reduce_only)  # noqa: F841
        log(f"✅ Closed position {symbol} — {quantity} units by MARKET.", level="INFO")

    except Exception as e:
        log(f"❌ Error while closing {symbol}: {str(e)}", level="ERROR")


trade_manager = TradeInfoManager()
monitored_stops = {}
monitored_stops_lock = threading.Lock()
open_positions_count = 0
dry_run_positions_count = 0
open_positions_lock = threading.Lock()
logged_trades = set()
logged_trades_lock = Lock()


def is_optimal_trading_hour():
    """
    Determine if current time is during peak trading hours.
    Returns True during high market activity hours.
    """
    current_time = datetime.now(pytz.UTC)
    hour_utc = current_time.hour

    # Check if current hour is in high activity hours list
    return hour_utc in HIGH_ACTIVITY_HOURS


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
    """
    Enhanced market regime detection with support for breakout detection.
    """
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

        # Calculate ADX for trend strength
        adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
        if len(adx_series) < 1 or adx_series.isna().all():
            log(
                f"{symbol} ⚠️ ADX calculation failed: insufficient data after processing",
                level="WARNING",
            )
            return "neutral"
        adx = adx_series.iloc[-1]

        # Calculate Bollinger Bands for volatility detection
        bb = ta.volatility.BollingerBands(df["close"], window=20)
        bb_width = (bb.bollinger_hband() - bb.bollinger_lband()).iloc[-1] / df["close"].iloc[-1] if not bb.bollinger_hband().empty and not bb.bollinger_lband().empty else 0

        log(f"{symbol} 🔍 Market regime: ADX = {adx:.2f}, BB Width = {bb_width:.4f}", level="DEBUG")

        # Breakout detection - wide BB width and strong ADX
        if BREAKOUT_DETECTION and bb_width > 0.05 and adx > 20:
            log(
                f"{symbol} 🔍 Breakout detected! (BB Width > 0.05, ADX > 20)",
                level="INFO",
            )
            return "breakout"
        elif adx > ADX_TREND_THRESHOLD:
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

    # Check trading hours if enabled
    if SHORT_TERM_MODE and not is_optimal_trading_hour():
        # For small accounts, still allow priority pairs during non-optimal hours
        balance = get_cached_balance()
        if balance < 150 and symbol in PRIORITY_SMALL_BALANCE_PAIRS:
            log(f"{symbol} Priority pair allowed during non-optimal hours", level="INFO")
        else:
            log(f"{symbol} ⏰ Skipping trade during non-optimal trading hours", level="INFO")
            send_telegram_message(f"⏰ Skipping {symbol}: non-optimal trading hours", force=True)
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

    # Get balance to determine account category
    balance = get_cached_balance()
    account_category = "Small" if balance < 150 else "Medium" if balance < 300 else "Standard"

    # Check if symbol is a priority pair for small accounts
    is_priority_pair = symbol in PRIORITY_SMALL_BALANCE_PAIRS if balance < 150 else False

    if account_category == "Small" and is_priority_pair:
        log(f"[Enter Trade] Priority pair {symbol} for small account", level="INFO")

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

        leverage_key = symbol.split(":")[0].replace("/", "") if USE_TESTNET else symbol.replace("/", "")
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

        # Add position size limitation
        account_balance = get_cached_balance()
        max_allowed_position = account_balance * 0.4  # Maximum 40% of balance per trade

        # Calculate notional value of the position
        notional = adjusted_qty * entry_price

        if notional > max_allowed_position:
            # Scale down the quantity to fit the maximum allowed position size
            old_qty = adjusted_qty
            adjusted_qty = max_allowed_position / entry_price
            notional = adjusted_qty * entry_price
            log(f"[Enter Trade] Position size for {symbol} reduced from {old_qty:.6f} to {adjusted_qty:.6f} to stay under 40% balance limit", level="WARNING")

        # Further protection: ensure all positions combined don't exceed 50% of balance
        current_positions_value = 0
        try:
            positions = exchange.fetch_positions()
            for pos in positions:
                if float(pos.get("contracts", 0)) != 0:
                    current_positions_value += abs(float(pos.get("contracts", 0)) * float(pos.get("entryPrice", 0)))
        except Exception as e:
            log(f"[Enter Trade] Failed to fetch current positions: {e}", level="ERROR")

        # Check if this new position would exceed 50% total allocation
        if (current_positions_value + notional) > (account_balance * 0.5):
            log(f"[Enter Trade] Skipping {symbol} - total position value would exceed 50% of balance", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: would exceed 50% balance limit", force=True)
            return

        balance = get_cached_balance()
        max_margin = balance * MAX_MARGIN_PERCENT
        required_margin = notional / leverage
        if required_margin > max_margin * 0.92:  # Increased from 0.9 to 0.92 for safety
            adjusted_qty = (max_margin * leverage * 0.92) / entry_price
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
                from core.binance_api import create_safe_market_order

                result = create_safe_market_order(symbol, side.lower(), qty)
                if not result["success"]:
                    log(f"[Enter Trade] Failed to open position for {symbol}: {result['error']}", level="ERROR")
                    send_telegram_message(f"❌ Failed to open trade {symbol}: {result['error']}", force=True)
                    return

                log(
                    f"[Enter Trade] Opened {side.upper()} position for {symbol}: qty={qty}, entry={entry_price}",
                    level="INFO",
                )
            except Exception as e:
                log(f"[Enter Trade] Failed to open position for {symbol}: {str(e)}", level="ERROR")
                send_telegram_message(f"❌ Failed to open trade {symbol}: {str(e)}", force=True)
                return

        # Use enhanced market regime detection
        regime = get_market_regime(symbol) if AUTO_TP_SL_ENABLED else None
        tp1_price, tp2_price, sl_price, qty_tp1_share, qty_tp2_share = calculate_tp_levels(entry_price, side, regime, score)

        # Check for None values
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

        # Enhanced commission and profit calculation for small accounts
        gross_profit_tp1 = qty_tp1 * abs(tp1_price - entry_price)
        commission = 2 * (qty * entry_price * TAKER_FEE_RATE)
        net_profit_tp1 = gross_profit_tp1 - commission
        commission_pct = (commission / (qty * entry_price)) * 100

        # Log enhanced details for small accounts
        if account_category == "Small":
            log(
                f"{symbol} Small Account Trade: Net profit on TP1: {net_profit_tp1:.2f} USDC, Commission: {commission:.6f} USDC ({commission_pct:.2f}%)",
                level="INFO",  # Increased from DEBUG to INFO for visibility
            )
        else:
            log(
                f"{symbol} Net profit on TP1: {net_profit_tp1:.2f} USDC, Commission: {commission:.2f} USDC",
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

            # Enhanced notification for small accounts
            if account_category == "Small":
                msg = (
                    r"✅ NEW TRADE" + (" (Re-entry)" if is_reentry else "") + r"\n"
                    r"Symbol: {symbol}\nSide: {side_upper}\nEntry: {entry_price}\n"
                    r"Qty: {qty}\nTP1: +{tp1_percent}%" + (r" / TP2: +{tp2_percent}%" if tp2_price and qty_tp2 > 0 else "") + r"\nSL: -{sl_percent}%\n"
                    r"Est. Profit: {net_profit:.2f} USDC\nComm: {commission:.6f} USDC ({commission_pct:.2f}%)"
                ).format(
                    symbol=symbol,
                    side_upper=side.upper(),
                    entry_price=round(entry_price, 4),
                    qty=qty,
                    tp1_percent=round(TP1_PERCENT * 100, 1),
                    tp2_percent=round(TP2_PERCENT * 100, 1) if tp2_price else "",
                    sl_percent=round(SL_PERCENT * 100, 1),
                    net_profit=net_profit_tp1,
                    commission=commission,
                    commission_pct=commission_pct,
                )
            else:
                msg = (
                    r"✅ NEW TRADE" + (" (Re-entry)" if is_reentry else "") + r"\n"
                    r"Symbol: {symbol}\nSide: {side_upper}\nEntry: {entry_price}\n"
                    r"Qty: {qty}\nTP1: +{tp1_percent}%" + (r" / TP2: +{tp2_percent}%" if tp2_price and qty_tp2 > 0 else "") + r"\nSL: -{sl_percent}%"
                ).format(
                    symbol=symbol,
                    side_upper=side.upper(),
                    entry_price=round(entry_price, 4),
                    qty=qty,
                    tp1_percent=round(TP1_PERCENT * 100, 1),
                    tp2_percent=round(TP2_PERCENT * 100, 1) if tp2_price else "",
                    sl_percent=round(SL_PERCENT * 100, 1),
                )
            send_telegram_message(msg, force=True)

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
            "account_category": account_category,  # Store account category for reference
            "commission": commission,  # Store commission for reference
            "net_profit_tp1": net_profit_tp1,  # Store expected profit for reference
            "market_regime": regime,  # Store market regime for reference
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

            # Start auto-profit monitoring thread
            threading.Thread(
                target=run_auto_profit_exit,
                args=(symbol, side, entry_price),
                daemon=True,
            ).start()

            # Start micro-trade monitoring thread
            if MICRO_PROFIT_ENABLED:
                threading.Thread(
                    target=run_micro_trade_monitor,
                    args=(symbol, side, entry_price, qty, start_time),
                    daemon=True,
                ).start()
                log(f"[DEBUG] Started micro-trade monitor for {symbol}", level="DEBUG")

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


def track_stop_loss(symbol, side, entry_price, qty, opened_at):
    with monitored_stops_lock:
        monitored_stops[symbol] = {
            "side": side,
            "entry": entry_price,
            "qty": qty,
            "opened_at": opened_at,
        }


def run_break_even(symbol, side, entry_price, tp_percent, check_interval=5):
    """
    Run break-even monitoring with earlier trigger (0.4 instead of 0.5).
    """
    target = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    # Using BREAKEVEN_TRIGGER (already set to 0.4 in config_loader)
    trigger = entry_price + (target - entry_price) * BREAKEVEN_TRIGGER if side == "buy" else entry_price - (entry_price - target) * BREAKEVEN_TRIGGER
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

            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
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
    """
    Enhanced trailing stop with breakout mode support.
    """
    try:
        # Fetch trade data to get market regime
        trade = trade_manager.get_trade(symbol)
        market_regime = trade.get("market_regime", "neutral") if trade else "neutral"

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
            atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range().iloc[-1]

            if pd.isna(atr) or atr == 0:
                atr = max([h - low for h, low in zip(highs, lows)])  # Fallback calculation

            adx_series = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
            if len(adx_series) < 1 or adx_series.isna().all():
                log(
                    f"[WARNING] ADX calculation failed for {symbol}: insufficient data after processing",
                    level="WARNING",
                )
                trailing_distance = entry_price * 0.02
            else:
                adx = adx_series.iloc[-1]

                # Adjust multiplier based on market regime
                if market_regime == "breakout":
                    # Tighter trailing stop for breakout mode to capture explosive moves
                    base_multiplier = 1.5
                    log(f"{symbol} 📊 Using tighter trailing stop for breakout mode", level="INFO")
                elif market_regime == "trend":
                    # Normal trailing for trend
                    base_multiplier = 2.0
                else:
                    # Wider trailing for flat or neutral
                    base_multiplier = 2.5

                # Further adjust based on aggressiveness
                multiplier = base_multiplier * (0.8 if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD else 1.0)

                trailing_distance = atr * multiplier
                log(f"{symbol} 📐 ADX: {adx:.1f}, Regime: {market_regime}, Trailing distance: {trailing_distance:.5f}")
    except Exception as e:
        log(f"[ERROR] Trailing init fallback: {e}", level="ERROR")
        trailing_distance = entry_price * 0.02

    highest = entry_price
    lowest = entry_price

    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
            if side == "buy":
                if price > highest:
                    highest = price
                    # For very profitable trades, tighten the trailing stop
                    profit_pct = (price - entry_price) / entry_price
                    if profit_pct > 0.03:  # Over 3% profit
                        trailing_distance *= 0.85  # Reduce trailing distance by 15%
                        log(f"{symbol} 📉 Tightening trailing stop due to high profit: {profit_pct:.2%}", level="DEBUG")

                if price <= highest - trailing_distance:
                    size = get_position_size(symbol)
                    safe_call_retry(
                        exchange.create_market_sell_order,
                        symbol,
                        size,
                        label=f"trailing_sell {symbol}",
                    )
                    send_telegram_message(f"📉 Trailing stop hit (LONG) {symbol} @ {price}", force=True)
                    record_trade_result(symbol, side, entry_price, price, "trailing")
                    break
            else:
                if price < lowest:
                    lowest = price
                    # For very profitable trades, tighten the trailing stop
                    profit_pct = (entry_price - price) / entry_price
                    if profit_pct > 0.03:  # Over 3% profit
                        trailing_distance *= 0.85  # Reduce trailing distance by 15%
                        log(f"{symbol} 📈 Tightening trailing stop due to high profit: {profit_pct:.2%}", level="DEBUG")

                if price >= lowest + trailing_distance:
                    size = get_position_size(symbol)
                    safe_call_retry(
                        exchange.create_market_buy_order,
                        symbol,
                        size,
                        label=f"trailing_buy {symbol}",
                    )
                    send_telegram_message(f"📈 Trailing stop hit (SHORT) {symbol} @ {price}", force=True)
                    record_trade_result(symbol, side, entry_price, price, "trailing")
                    break
            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Adaptive trailing error for {symbol}: {e}", level="ERROR")
            break


def run_soft_exit(symbol, side, entry_price, tp1_percent, qty, check_interval=5):
    """
    Enhanced soft exit with earlier profit taking.
    """
    global open_positions_count, dry_run_positions_count
    tp1_price = entry_price * (1 + tp1_percent) if side == "buy" else entry_price * (1 - tp1_percent)

    # Use SOFT_EXIT_THRESHOLD (already set to 0.7 in config_loader, was 0.8 previously)
    soft_exit_price = entry_price + (tp1_price - entry_price) * SOFT_EXIT_THRESHOLD if side == "buy" else entry_price - (entry_price - tp1_price) * SOFT_EXIT_THRESHOLD

    # Use SOFT_EXIT_SHARE (typically 0.5 - close half position)
    soft_exit_qty = qty * SOFT_EXIT_SHARE

    log(
        f"[Soft Exit] Monitoring {symbol}: entry={entry_price}, tp1_price={tp1_price}, " f"soft_exit_price={soft_exit_price}, soft_exit_qty={soft_exit_qty}",
        level="DEBUG",
    )

    # Dynamic check interval - more frequent during optimal trading hours
    dynamic_check_interval = check_interval // 2 if is_optimal_trading_hour() else check_interval

    trade_closed = False
    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
            log(
                f"[Soft Exit] Checking {symbol}: current price={price}, soft_exit_price={soft_exit_price}",
                level="DEBUG",
            )

            if (side == "buy" and price >= soft_exit_price) or (side == "sell" and price <= soft_exit_price):
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

                    # For small accounts, consider moving stop loss to entry price
                    trade = trade_manager.get_trade(symbol)
                    if trade and trade.get("account_category") == "Small":
                        try:
                            # Cancel any existing stop orders
                            open_orders = exchange.fetch_open_orders(symbol)
                            stop_orders = [o for o in open_orders if o["type"].upper() == "STOP_MARKET" or o["type"].upper() == "STOP"]

                            for order in stop_orders:
                                exchange.cancel_order(order["id"], symbol)
                                log(f"[Soft Exit] Cancelled stop order {order['id']} for {symbol}", level="INFO")

                            # Set new stop at entry price (break-even)
                            remaining_position = get_position_size(symbol)
                            if remaining_position > 0:
                                safe_call_retry(
                                    exchange.create_order,
                                    symbol,
                                    "STOP_MARKET",
                                    "sell" if side == "buy" else "buy",
                                    remaining_position,
                                    params={"stopPrice": entry_price, "reduceOnly": True},
                                    label=f"soft_exit_break_even {symbol}",
                                )
                                log(f"[Soft Exit] Set break-even stop for remaining position in {symbol}", level="INFO")
                                send_telegram_message(f"🔒 Break-even stop set for remaining position in {symbol}", force=True)
                        except Exception as e:
                            log(f"[Soft Exit] Failed to adjust stop orders for {symbol}: {e}", level="ERROR")

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

            # Use dynamic check interval
            time.sleep(dynamic_check_interval)
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

    # Enhanced trade result logging with account category
    account_category = trade.get("account_category", "Standard")
    commission = trade.get("commission", 0)

    # Calculate absolute profit for small accounts
    qty = trade.get("qty", 0)
    absolute_profit = (exit_price - entry_price) * qty if side == "buy" else (entry_price - exit_price) * qty
    net_absolute_profit = absolute_profit - commission

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
        account_category=account_category,
        net_profit_usdc=round(net_absolute_profit, 2) if account_category == "Small" else None,
    )

    # Enhanced notification with absolute profit for small accounts
    if account_category == "Small":
        msg = (
            f"📤 *Trade Closed* [{final_result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}]\n"
            f"• {symbol} — {side.upper()}\n"
            f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
            f"• PnL: {round(pnl, 2)}% | ${round(net_absolute_profit, 2)} USDC\n"
            f"• Held: {duration} min"
        )
    else:
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
        exit_price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
        record_trade_result(symbol, trade["side"], trade["entry"], exit_price, "manual")
        log(f"[DRY] Closed {symbol} at {exit_price}", level="INFO")
        send_telegram_message(f"DRY RUN: Closed {symbol} at {exit_price}", force=True)
        trade_manager.set_last_closed_time(symbol, time.time())


def close_real_trade(symbol):
    # Load state to check if bot is stopping
    state = load_state()
    trade = trade_manager.get_trade(symbol)

    # Skip warning if in stopping mode
    if not trade:
        if not state.get("stopping") and not state.get("shutdown"):
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
                    safe_call_retry(exchange.create_market_sell_order, symbol, qty, label=f"close_sell {symbol}")
                else:
                    safe_call_retry(exchange.create_market_buy_order, symbol, qty, label=f"close_buy {symbol}")

            entry_price = trade["entry"]
            pnl_percent = ((exit_price - entry_price) / entry_price * 100) if side == "buy" else ((entry_price - exit_price) / entry_price * 100)
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
                send_telegram_message(f"❌ Failed to cancel order for {symbol}: {str(e)}", force=True)

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


def run_auto_profit_exit(symbol, side, entry_price, check_interval=5):
    """
    Monitor position profit and automatically close when it reaches the profit threshold.

    Args:
        symbol: Trading pair symbol
        side: Position side (buy/sell)
        entry_price: Position entry price
        check_interval: How often to check profit (in seconds)
    """
    log(f"[Auto-Profit] Starting profit monitoring for {symbol} with entry price {entry_price}", level="DEBUG")

    while True:
        try:
            # Check if trade still exists
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"[Auto-Profit] Trade for {symbol} no longer exists, stopping auto-profit thread", level="INFO")
                break

            # Check if position is still open
            position = get_position_size(symbol)
            if position <= 0:
                log(f"[Auto-Profit] Position for {symbol} closed, stopping auto-profit thread", level="INFO")
                break

            # Get current price and calculate profit percentage
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]

            if side.lower() == "buy":
                profit_percentage = ((price - entry_price) / entry_price) * 100
            else:  # side == "sell"
                profit_percentage = ((entry_price - price) / entry_price) * 100

            log(f"[Auto-Profit] {symbol} current profit: {profit_percentage:.2f}%", level="DEBUG")

            # Check against thresholds
            if profit_percentage >= BONUS_PROFIT_THRESHOLD:
                log(f"🎉 BONUS PROFIT! Auto-closing {symbol} at +{profit_percentage:.2f}% 🚀", level="INFO")
                safe_close_trade(exchange, symbol, trade)
                send_telegram_message(f"🎉 *Bonus Profit!* {symbol} closed at +{profit_percentage:.2f}% 🚀\n" f"Reason: Exceeded {BONUS_PROFIT_THRESHOLD}% profit!")
                break
            elif profit_percentage >= AUTO_CLOSE_PROFIT_THRESHOLD:
                log(f"✅ Auto-closing {symbol} at +{profit_percentage:.2f}% (Threshold: {AUTO_CLOSE_PROFIT_THRESHOLD}%)", level="INFO")
                safe_close_trade(exchange, symbol, trade)
                send_telegram_message(f"✅ *Auto-closed* {symbol} at +{profit_percentage:.2f}% profit 🚀\n" f"Reason: Reached profit target {AUTO_CLOSE_PROFIT_THRESHOLD}%")
                break

            # Wait before checking again
            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Auto-profit error for {symbol}: {e}", level="ERROR")
            break


def run_micro_trade_monitor(symbol, side, entry_price, qty, start_time, check_interval=10):
    """Monitor micro-trades for time-based exits."""

    if not MICRO_PROFIT_ENABLED:
        return

    # Проверить, является ли позиция микро-сделкой
    balance = get_cached_balance()
    position_value = qty * entry_price
    position_percentage = position_value / balance if balance > 0 else 0

    if position_percentage >= MICRO_TRADE_SIZE_THRESHOLD:
        log(f"{symbol} Not a micro-trade ({position_percentage:.2%} of balance)", level="DEBUG")
        return

    log(f"{symbol} 🔍 Starting micro-trade monitor (timeout: {MICRO_TRADE_TIMEOUT_MINUTES}min)", level="INFO")

    while True:
        try:
            # Проверить, существует ли еще позиция
            position_size = get_position_size(symbol)
            if position_size <= 0:
                break

            # Проверить прошедшее время
            current_time = time.time()
            elapsed_minutes = (current_time - start_time.timestamp()) / 60

            if elapsed_minutes >= MICRO_TRADE_TIMEOUT_MINUTES:
                # Получить текущую цену и рассчитать прибыль
                price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"micro_trade_monitor {symbol}")

                if not price:
                    log(f"Failed to fetch price for {symbol} during micro-trade monitor", level="WARNING")
                    break

                current_price = price["last"]

                if side.lower() == "buy":
                    profit_percent = ((current_price - entry_price) / entry_price) * 100
                else:
                    profit_percent = ((entry_price - current_price) / entry_price) * 100

                # Закрыть только если достигнут минимальный профит
                if profit_percent >= MICRO_PROFIT_THRESHOLD:
                    log(f"{symbol} 🕒 Micro-trade timeout reached with {profit_percent:.2f}% profit", level="INFO")

                    # Использовать safe_close_trade вместо create_market_order
                    trade_data = trade_manager.get_trade(symbol)
                    if trade_data:
                        safe_close_trade(exchange, symbol, trade_data)

                    send_telegram_message(f"⏰ Micro-trade timeout: {symbol} closed at +{profit_percent:.2f}%", force=True)
                    break

            time.sleep(check_interval)

        except Exception as e:
            log(f"[ERROR] Micro-trade monitor error for {symbol}: {e}", level="ERROR")
            break


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
                send_telegram_message(f"❌ Failed to close all positions during panic: {e}", force=True)

    trade_manager._trades.clear()
    initialize_cache()
    log("Panic close executed: All trades closed, counters reset", level="INFO")
    send_telegram_message("🚨 *Panic Close Executed*:\nAll positions closed.", force=True)

    stop_event.set()
    os._exit(0)


# Add auto-profit exit logic in your position monitoring loop
# This would typically be in the section that monitors existing positions
# For example, in the main trading cycle:

"""
# Example of where to add the auto-profit check in your monitoring loop:
for symbol in active_trades:
    # Get current price and calculate PnL
    current_price = get_current_price(symbol)
    trade_data = active_trades[symbol]
    entry_price = trade_data['entry']
    side = trade_data['side']

    # Calculate position PnL percentage
    position_pnl_percentage = ((current_price - entry_price) / entry_price * 100) if side == "buy" else ((entry_price - current_price) / entry_price * 100)

    # Auto-profit exit checks
    if position_pnl_percentage >= BONUS_PROFIT_THRESHOLD:
        log(f"🎉 BONUS PROFIT! Auto-closing {symbol} at +{position_pnl_percentage:.2f}% 🚀", level="INFO")
        safe_close_trade(exchange, symbol, active_trades[symbol])
        send_telegram_message(
            f"🎉 *Bonus Profit!* {symbol} closed at +{position_pnl_percentage:.2f}% 🚀\n"
            f"Reason: Exceeded {BONUS_PROFIT_THRESHOLD}% profit!"
        )
        continue
    elif position_pnl_percentage >= AUTO_CLOSE_PROFIT_THRESHOLD:
        log(f"✅ Auto-closing {symbol} at +{position_pnl_percentage:.2f}% (Threshold: {AUTO_CLOSE_PROFIT_THRESHOLD}%)", level="INFO")
        safe_close_trade(exchange, symbol, active_trades[symbol])
        send_telegram_message(
            f"✅ *Auto-closed* {symbol} at +{position_pnl_percentage:.2f}% profit 🚀\n"
            f"Reason: Reached profit target {AUTO_CLOSE_PROFIT_THRESHOLD}%"
        )
        continue
"""
