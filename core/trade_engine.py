# trade_engine.py
import os
import threading
import time
import traceback
from datetime import datetime
from threading import Lock

import pandas as pd
import ta

from common.config_loader import (
    ADX_FLAT_THRESHOLD,
    ADX_TREND_THRESHOLD,
    AGGRESSIVENESS_THRESHOLD,
    AUTO_CLOSE_PROFIT_THRESHOLD,
    AUTO_TP_SL_ENABLED,
    BONUS_PROFIT_THRESHOLD,
    BREAKEVEN_TRIGGER,
    BREAKOUT_DETECTION,
    DRY_RUN,
    ENABLE_BREAKEVEN,
    ENABLE_TRAILING,
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
    SHORT_TERM_MODE,
    SL_PERCENT,
    SOFT_EXIT_ENABLED,
    SOFT_EXIT_SHARE,
    SOFT_EXIT_THRESHOLD,
    TAKER_FEE_RATE,
    TP1_PERCENT,
    TP2_PERCENT,
    USE_TESTNET,
    get_priority_small_balance_pairs,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.binance_api import fetch_ohlcv
from core.exchange_init import exchange

# Additional required imports
from core.position_manager import can_open_new_position
from core.risk_utils import get_adaptive_risk_percent
from core.tp_utils import calculate_tp_levels
from telegram.telegram_utils import send_telegram_message
from tp_logger import log_trade_result
from utils_core import (
    get_cached_balance,
    get_cached_positions,
    initialize_cache,
    is_optimal_trading_hour,
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


# Global variables
trade_manager = TradeInfoManager()
monitored_stops = {}
monitored_stops_lock = threading.Lock()
open_positions_count = 0
dry_run_positions_count = 0
open_positions_lock = threading.Lock()
logged_trades = set()
logged_trades_lock = Lock()


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
        binance_client.futures_create_order(symbol=symbol.replace("/", ""), side=close_side, type="MARKET", quantity=quantity, reduceOnly=reduce_only)
        log(f"✅ Closed position {symbol} — {quantity} units by MARKET.", level="INFO")

    except Exception as e:
        log(f"❌ Error while closing {symbol}: {str(e)}", level="ERROR")


def safe_close_trade(binance_client, symbol, trade_data, reason="manual"):
    """
    Safely close a trade by cancelling all orders and closing the position.
    This ensures clean exits without lingering orders.
    """
    try:
        side = trade_data["side"]
        quantity = trade_data["quantity"]
        entry_price = trade_data.get("entry", 0)

        # Get current price for exit
        ticker = safe_call_retry(exchange.fetch_ticker, symbol)
        exit_price = ticker["last"] if ticker else None

        # Close the position
        close_trade_and_cancel_orders(binance_client=binance_client, symbol=symbol, side=side, quantity=quantity)

        # Record the trade result BEFORE removing from manager
        if exit_price:
            # Calculate PnL for success tracking
            if side.lower() == "buy":
                final_pnl = (exit_price - entry_price) * quantity
            else:
                final_pnl = (entry_price - exit_price) * quantity

            record_trade_result(symbol, side, entry_price, exit_price, reason)

            # Success tracking for symbol blocking system
            if reason == "hit_tp" and final_pnl > 0:
                # Reset failure count for this symbol on profitable TP exit
                from core.fail_stats_tracker import reset_failure_count

                # Normalize symbol format if needed (BTCUSDC -> BTC/USDC)
                normalized_symbol = symbol
                if "/" not in symbol and "USDC" in symbol:
                    normalized_symbol = symbol.replace("USDC", "/USDC")

                reset_failure_count(normalized_symbol)
                log(f"[TradeEngine] ✅ Reset failure count for {normalized_symbol} after TP profit of {final_pnl:.2f}", level="INFO")

        # Remove from trade manager
        trade_manager._trades.pop(symbol, None)
        log(f"✅ Safe close complete for {symbol} (reason: {reason})", level="INFO")

    except Exception as e:
        log(f"❌ Error during safe close for {symbol}: {str(e)}", level="ERROR")


def calculate_risk_amount(balance, risk_percent=None, symbol=None, atr_percent=None, volume_usdc=None, score=0):
    """
    Enhanced risk amount calculation using the optimized risk parameters

    Args:
        balance (float): Current account balance
        risk_percent (float, optional): Risk percentage override
        symbol (str, optional): Trading pair symbol
        atr_percent (float, optional): ATR percentage of the pair
        volume_usdc (float, optional): 24h volume in USDC
        score (float, optional): Signal quality score

    Returns:
        float: Risk amount in USDC
    """
    # Get win streak from trade stats
    from common.config_loader import trade_stats

    win_streak = trade_stats.get("streak_win", 0)

    # If risk_percent is not provided, calculate it adaptively
    if risk_percent is None:
        risk_percent = get_adaptive_risk_percent(balance, atr_percent=atr_percent, volume_usdc=volume_usdc, win_streak=win_streak, score=score)

    log(f"Using risk percentage: {risk_percent*100:.2f}% for balance: {balance:.2f} USDC", level="DEBUG")
    return balance * risk_percent


def calculate_position_size(entry_price, stop_price, risk_amount, symbol=None):
    """Calculate position size with graduated risk adjustment."""
    if entry_price <= 0 or stop_price <= 0:
        return 0

    # Apply risk factor if symbol provided
    risk_factor = 1.0
    if symbol:
        # Import here to avoid circular imports
        from core.fail_stats_tracker import get_symbol_risk_factor

        risk_factor, _ = get_symbol_risk_factor(symbol)

        if risk_factor < 1.0:
            log(f"Applied risk reduction to {symbol}: {risk_factor:.2f}x position size", level="INFO")

    # Adjust risk amount by risk factor
    adjusted_risk = risk_amount * risk_factor

    # Standard position size calculation
    price_delta = abs(entry_price - stop_price)
    if price_delta == 0:
        return 0

    position_size = adjusted_risk / price_delta
    return position_size


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
        if balance < 150 and symbol in get_priority_small_balance_pairs():
            log(f"{symbol} Priority pair allowed during non-optimal hours", level="INFO")
        else:
            log(f"{symbol} ⏰ Skipping trade during non-optimal trading hours", level="INFO")
            send_telegram_message(f"⏰ Skipping {symbol}: non-optimal trading hours", force=True)
            return

    # Check position limits based on account size
    balance = get_cached_balance()
    if not can_open_new_position(balance):
        log(f"[Skip] Position limit reached for account balance: {balance:.2f} USDC", level="INFO")
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
    is_priority_pair = symbol in get_priority_small_balance_pairs() if account_category in ("Small", "Medium") else False

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

        # === INSERT HERE ===
        from core.fail_stats_tracker import get_symbol_risk_factor
        from telegram.telegram_utils import escape_markdown_v2

        risk_factor, _ = get_symbol_risk_factor(symbol)
        from core.risk_utils import get_adaptive_risk_percent

        risk_percent = get_adaptive_risk_percent(balance, symbol=symbol)

        adjusted_risk = balance * risk_percent * risk_factor

        log(f"🧠 {symbol} | risk_factor={risk_factor:.2f} → scaled risk={adjusted_risk:.2f} USDC", level="INFO")

        if risk_factor < 0.9:
            send_telegram_message(f"🔹 *{escape_markdown_v2(symbol)}* opened with `risk_factor={risk_factor:.2f}`\\n" f"💰 Adjusted position risk: *{adjusted_risk:.2f} USDC*", force=True)

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

        # Use standardized capital utilization check - UPDATED FOR PHASE 1.5
        from core.risk_utils import check_capital_utilization

        if not check_capital_utilization(account_balance, notional):
            log(f"[Enter Trade] Skipping {symbol} due to capital utilization risk", level="WARNING")
            send_telegram_message(f"⚠️ Skipping {symbol}: capital utilization limit exceeded", force=True)
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
                from threading import Thread

                from core.binance_api import create_safe_market_order
                from core.trade_engine import run_auto_profit_exit  # Ensure this is imported

                result = create_safe_market_order(symbol, side.lower(), qty)
                if not result["success"]:
                    log(f"[Enter Trade] Failed to open position for {symbol}: {result['error']}", level="ERROR")
                    send_telegram_message(f"❌ Failed to open trade {symbol}: {result['error']}", force=True)
                    return

                log(
                    f"[Enter Trade] Opened {side.upper()} position for {symbol}: qty={qty}, entry={entry_price}",
                    level="INFO",
                )

                # === Start Auto-Profit Thread ===
                Thread(target=run_auto_profit_exit, args=(symbol, side, entry_price), daemon=True).start()
                log(f"[Auto-Profit] Started monitoring thread for {symbol}", level="DEBUG")

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
            # Use post-only limit orders for TP levels - UPDATED FOR PHASE 1.5
            from core.order_utils import create_post_only_limit_order

            if qty_tp1 > 0:
                create_post_only_limit_order(symbol, "sell" if side == "buy" else "buy", qty_tp1, tp1_price)
            if tp2_price and qty_tp2 > 0:
                create_post_only_limit_order(symbol, "sell" if side == "buy" else "buy", qty_tp2, tp2_price)
            # SL remains as STOP_MARKET order
            safe_call_retry(
                exchange.create_order,
                symbol,
                "STOP_MARKET",
                "sell" if side == "buy" else "buy",
                qty,
                params={"stopPrice": round(sl_price, 4), "reduceOnly": True},
                label=f"create_stop_order {symbol}",
            )

            from telegram.telegram_utils import escape_markdown_v2  # в начале файла

        # Enhanced notification for small accounts
        if account_category == "Small":
            msg = (
                "🚀 *NEW TRADE OPENED*{}\n"
                "📊 *Symbol:* `{}`\n"
                "🧭 *Side:* `{}`\n"
                "🎯 *Entry:* `{}`\n"
                "📦 *Qty:* `{}`\n"
                "🏁 *TP1:* `+{}%`{}\n"
                "🛑 *SL:* `-{}%`\n"
                "💸 *Est. Profit:* `{:.2f}` USDC\n"
                "🧾 *Commission:* `{:.6f}` USDC (`{:.2f}%`)"
            ).format(
                " (Re-entry)" if is_reentry else "",
                escape_markdown_v2(symbol),
                escape_markdown_v2(side.upper()),
                round(entry_price, 4),
                qty,
                round(TP1_PERCENT * 100, 1),
                f" / TP2: `+{round(TP2_PERCENT * 100, 1)}%`" if tp2_price and qty_tp2 > 0 else "",
                round(SL_PERCENT * 100, 1),
                net_profit_tp1,
                commission,
                commission_pct,
            )
        else:
            msg = ("🚀 *NEW TRADE OPENED*{}\n" "📊 *Symbol:* `{}`\n" "🧭 *Side:* `{}`\n" "🎯 *Entry:* `{}`\n" "📦 *Qty:* `{}`\n" "🏁 *TP1:* `+{}%`{}\n" "🛑 *SL:* `-{}%`").format(
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
            "account_category": account_category,  # Store account category for reference
            "commission": commission,  # Store commission for reference
            "net_profit_tp1": net_profit_tp1,  # Store expected profit for reference
            "market_regime": regime,  # Store market regime for reference
            "quantity": qty,  # Add quantity field for safe_close_trade
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

            # Start micro-profit monitoring thread
            if MICRO_PROFIT_ENABLED:
                threading.Thread(
                    target=run_micro_profit_optimizer,
                    args=(symbol, side, entry_price, qty, start_time),
                    daemon=True,
                ).start()
                log(f"[DEBUG] Started micro-profit monitor for {symbol}", level="DEBUG")

            # Start dynamic position management thread
            threading.Thread(
                target=monitor_active_position,
                args=(symbol, side, entry_price, qty, start_time),
                daemon=True,
            ).start()
            log(f"[DEBUG] Started dynamic position management for {symbol}", level="DEBUG")

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
    Run break-even monitoring with earlier trigger (0.3 instead of 0.4).
    """
    target = entry_price * (1 + tp_percent) if side == "buy" else entry_price * (1 - tp_percent)
    # Using BREAKEVEN_TRIGGER (updated to 0.30 in config_loader)
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
    Enhanced trailing stop with breakout mode support and empty position protection.
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
            # Empty position protection - check if position exists
            position = None
            try:
                positions = get_cached_positions()
                for pos in positions:
                    if pos["symbol"] == symbol:
                        position = pos
                        break
            except Exception as e:
                log(f"[ERROR] Failed to fetch position for {symbol} in trailing stop: {e}", level="ERROR")

            # Check if position exists and has non-zero size
            if not position or float(position.get("positionAmt", 0)) == 0 or float(position.get("contracts", 0)) == 0:
                log(f"{symbol} ⚠️ Trailing cancelled: No open position or zero size.", level="DEBUG")
                break

            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
            if side == "buy":
                # Trailing for long positions
                if price > highest:
                    highest = price
                    # For very profitable trades, tighten the trailing stop
                    profit_pct = (price - entry_price) / entry_price
                    if profit_pct > 0.03:  # Over 3% profit
                        trailing_distance *= 0.85  # Reduce trailing distance by 15%
                        log(f"{symbol} 📉 Tightening trailing stop due to high profit: {profit_pct:.2%}", level="DEBUG")

                if price <= highest - trailing_distance:
                    size = get_position_size(symbol)
                    if size <= 0:
                        log(f"{symbol} ⚠️ Trailing sell cancelled: Position already closed.", level="DEBUG")
                        break

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
                # Trailing for short positions
                if price < lowest:
                    lowest = price
                    # For very profitable trades, tighten the trailing stop
                    profit_pct = (entry_price - price) / entry_price
                    if profit_pct > 0.03:  # Over 3% profit
                        trailing_distance *= 0.85  # Reduce trailing distance by 15%
                        log(f"{symbol} 📈 Tightening trailing stop due to high profit: {profit_pct:.2%}", level="DEBUG")

                if price >= lowest + trailing_distance:
                    size = get_position_size(symbol)
                    if size <= 0:
                        log(f"{symbol} ⚠️ Trailing buy cancelled: Position already closed.", level="DEBUG")
                        break

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
    Enhanced soft exit with earlier profit taking and cleanup of stop orders.
    """
    global open_positions_count, dry_run_positions_count
    tp1_price = entry_price * (1 + tp1_percent) if side == "buy" else entry_price * (1 - tp1_percent)
    soft_exit_price = entry_price + (tp1_price - entry_price) * SOFT_EXIT_THRESHOLD if side == "buy" else entry_price - (entry_price - tp1_price) * SOFT_EXIT_THRESHOLD
    soft_exit_qty = qty * SOFT_EXIT_SHARE

    log(f"[Soft Exit] Monitoring {symbol}: entry={entry_price}, tp1_price={tp1_price}, " f"soft_exit_price={soft_exit_price}, soft_exit_qty={soft_exit_qty}", level="DEBUG")

    dynamic_check_interval = check_interval // 2 if is_optimal_trading_hour() else check_interval
    trade_closed = False

    while True:
        try:
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]
            log(f"[Soft Exit] Checking {symbol}: current price={price}, soft_exit_price={soft_exit_price}", level="DEBUG")

            if (side == "buy" and price >= soft_exit_price) or (side == "sell" and price <= soft_exit_price):
                if DRY_RUN:
                    log(f"[DRY] Soft Exit triggered for {symbol} at {price}: closing {soft_exit_qty}", level="INFO")
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

                    # 🔧 Cancel remaining orders after soft exit
                    try:
                        exchange.futures_cancel_all_open_orders(symbol=symbol.replace("/", ""))
                        log(f"[Soft Exit] Canceled all remaining orders for {symbol}", level="INFO")
                    except Exception as e:
                        log(f"[Soft Exit] Error canceling orders for {symbol}: {e}", level="WARNING")

                    if not trade_closed:
                        record_trade_result(symbol, side, entry_price, price, "soft_exit")
                        trade_closed = True

                    # Place protective stop loss for remaining position
                    position = get_position_size(symbol)
                    if position > 0:
                        stop_side = "sell" if side == "buy" else "buy"
                        stop_level = entry_price  # Set stop at entry level (breakeven)
                        try:
                            safe_call_retry(
                                exchange.create_order,
                                symbol,
                                "STOP_MARKET",
                                stop_side,
                                position,
                                params={"stopPrice": round(stop_level, 4), "reduceOnly": True},
                                label=f"protective_stop_{symbol}",
                            )
                            log(f"[Soft Exit] Protective SL placed at {stop_level:.4f} for remaining position", level="INFO")
                        except Exception as e:
                            log(f"[Soft Exit] Failed to place protective stop: {e}", level="ERROR")

                    log(f"[Soft Exit] Remaining position size for {symbol}: {position}", level="DEBUG")
                    if position <= 0:
                        trade_manager.remove_trade(symbol)
                        log(f"[Soft Exit] Fully closed {symbol}, removed from trade_manager", level="INFO")
                        initialize_cache()
                        break

            time.sleep(dynamic_check_interval)

        except Exception as e:
            log(f"[ERROR] Soft Exit error for {symbol}: {e}", level="ERROR")
            break


def record_trade_result(symbol, side, entry_price, exit_price, result_type):
    """
    Record trade result with enhanced exit reason categorization.
    Adds support for 'flat' exit type for trades that don't hit TP/SL targets.
    """
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

    # Determine exit reason
    if trade.get("tp1_hit", False) or trade.get("tp2_hit", False):
        exit_reason = "tp"
    elif result_type == "sl":
        exit_reason = "sl"
    else:
        # This is a flat exit - neither TP nor SL was hit
        exit_reason = "flat"

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
        exit_reason=exit_reason,  # Added exit_reason parameter
    )

    # Enhanced notification with exit reason for better clarity
    exit_reason_display = f" [{exit_reason.upper()}]" if exit_reason else ""

    # Enhanced notification with absolute profit for small accounts
    if account_category == "Small":
        msg = (
            f"📤 *Trade Closed* [{final_result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}{exit_reason_display}]\n"
            f"• {symbol} — {side.upper()}\n"
            f"• Entry: {round(entry_price, 4)} → Exit: {round(exit_price, 4)}\n"
            f"• PnL: {round(pnl, 2)}% | ${round(net_absolute_profit, 2)} USDC\n"
            f"• Held: {duration} min"
        )
    else:
        msg = (
            f"📤 *Trade Closed* [{final_result_type.upper()}{' + Soft Exit' if trade.get('soft_exit_hit', False) else ''}{exit_reason_display}]\n"
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
    Enhanced with TP1 protection and 60-minute time limit to avoid interfering with TP2.
    """
    log(f"[Auto-Profit] Starting profit monitoring for {symbol} with entry price {entry_price}", level="DEBUG")
    time.time()

    while True:
        try:
            # Get current trade object
            trade = trade_manager.get_trade(symbol)
            if not trade:
                log(f"[Auto-Profit] Trade for {symbol} no longer exists, stopping auto-profit thread", level="INFO")
                break

            # === TP1 Protection ===
            if trade.get("tp1_hit"):
                log(f"[Auto-Profit] TP1 already hit for {symbol}, stopping auto-profit to let TP2 work", level="INFO")
                break

            # === Time Limit Check ===
            trade_start = trade.get("start_time")
            if trade_start:
                duration = (time.time() - trade_start.timestamp()) / 60
                if duration > 60:
                    log(f"[Auto-Profit] 60-minute time limit reached for {symbol}, stopping auto-profit thread", level="INFO")
                    break

            # Check if position still open
            position = get_position_size(symbol)
            if position <= 0:
                log(f"[Auto-Profit] Position for {symbol} closed, stopping auto-profit thread", level="INFO")
                break

            # Get current price
            price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"fetch_ticker {symbol}")["last"]

            if side.lower() == "buy":
                profit_percentage = ((price - entry_price) / entry_price) * 100
            else:
                profit_percentage = ((entry_price - price) / entry_price) * 100

            log(f"[Auto-Profit] {symbol} current profit: {profit_percentage:.2f}%", level="DEBUG")

            # === Profit Thresholds ===
            if profit_percentage >= BONUS_PROFIT_THRESHOLD:
                log(f"🎉 BONUS PROFIT! Auto-closing {symbol} at +{profit_percentage:.2f}% 🚀", level="INFO")
                safe_close_trade(exchange, symbol, trade, reason="bonus_profit")
                send_telegram_message(f"🎉 *Bonus Profit!* {symbol} closed at +{profit_percentage:.2f}% 🚀\nReason: Exceeded {BONUS_PROFIT_THRESHOLD}% profit!")
                break
            elif profit_percentage >= AUTO_CLOSE_PROFIT_THRESHOLD:
                log(f"✅ Auto-closing {symbol} at +{profit_percentage:.2f}% (Threshold: {AUTO_CLOSE_PROFIT_THRESHOLD}%)", level="INFO")
                safe_close_trade(exchange, symbol, trade, reason="auto_profit")
                send_telegram_message(f"✅ *Auto-closed* {symbol} at +{profit_percentage:.2f}% profit 🚀\nReason: Reached profit target {AUTO_CLOSE_PROFIT_THRESHOLD}%")
                break

            time.sleep(check_interval)

        except Exception as e:
            log(f"[ERROR] Auto-profit error for {symbol}: {e}", level="ERROR")
            break


def check_auto_profit(trade, threshold=AUTO_CLOSE_PROFIT_THRESHOLD):
    """
    Advanced auto-profit check:
    - Skips if TP1 already hit (let TP2 work)
    - Applies only if position open less than 60 min
    - Applies only if profit threshold is reached
    """
    if not trade:
        return False

    # TP1 protection
    if trade.get("tp1_hit"):
        return False

    # Time limit protection
    start_time = trade.get("start_time")
    if not start_time:
        return False

    duration = (time.time() - start_time.timestamp()) / 60
    if duration > 60:
        return False

    # Get current price
    symbol = trade.get("symbol")
    entry_price = trade.get("entry", 0)
    side = trade.get("side")

    ticker = safe_call_retry(exchange.fetch_ticker, symbol)
    current_price = ticker["last"] if ticker else 0

    if not entry_price or not current_price:
        return False

    # Calculate profit percentage
    pnl = (current_price - entry_price) / entry_price if side == "buy" else (entry_price - current_price) / entry_price

    if pnl >= threshold:
        log(f"[AutoProfit] Triggered for {symbol}: pnl={pnl:.2%}, duration={duration:.1f} min", level="INFO")
        return True

    return False


def run_micro_profit_optimizer(symbol, side, entry_price, qty, start_time, check_interval=5):
    if not MICRO_PROFIT_ENABLED:
        return

    # Calculate position size percentage of account balance
    balance = get_cached_balance()
    position_value = qty * entry_price
    position_percentage = position_value / balance if balance > 0 else 0

    # Skip if not a micro-trade
    if position_percentage >= MICRO_TRADE_SIZE_THRESHOLD:
        log(f"{symbol} Not a micro-trade ({position_percentage:.2%} of balance)", level="DEBUG")
        return

    # Используем MICRO_PROFIT_THRESHOLD как базовое значение
    base_threshold = MICRO_PROFIT_THRESHOLD  # 0.3% по умолчанию
    if position_percentage < 0.15:  # Very small position
        profit_threshold = base_threshold  # Оставляем как есть (0.3%)
    elif position_percentage < 0.25:
        profit_threshold = base_threshold * 1.33  # Увеличиваем до ~0.4%
    else:
        profit_threshold = base_threshold * 1.67  # Увеличиваем до ~0.5%

    log(f"{symbol} 🔍 Starting micro-profit optimizer with {profit_threshold:.1f}% threshold", level="INFO")

    while True:
        try:
            # Check if position still exists
            position_size = get_position_size(symbol)
            if position_size <= 0:
                log(f"{symbol} Position closed, ending micro-profit optimizer", level="DEBUG")
                break

            # Check elapsed time
            current_time = time.time()
            elapsed_minutes = (current_time - start_time.timestamp()) / 60

            if elapsed_minutes >= MICRO_TRADE_TIMEOUT_MINUTES:
                # Get current price and calculate profit
                price = safe_call_retry(exchange.fetch_ticker, symbol, label=f"micro_profit_optimizer {symbol}")
                if not price:
                    log(f"Failed to fetch price for {symbol} during micro-profit optimization", level="WARNING")
                    break

                current_price = price["last"]

                # Calculate profit percentage
                if side.lower() == "buy":
                    profit_percent = ((current_price - entry_price) / entry_price) * 100
                else:
                    profit_percent = ((entry_price - current_price) / entry_price) * 100

                # Close if profit threshold reached
                if profit_percent >= profit_threshold:
                    log(f"{symbol} 🕒 Micro-trade timeout reached with {profit_percent:.2f}% profit", level="INFO")

                    # Get trade data and use safe_close_trade
                    trade_data = trade_manager.get_trade(symbol)
                    if trade_data:
                        safe_close_trade(exchange, symbol, trade_data, reason="micro_profit")
                        send_telegram_message(f"⏰ Micro-profit target: {symbol} closed at +{profit_percent:.2f}%", force=True)
                    break
                else:
                    log(f"{symbol} ❎ Micro-trade timeout with only {profit_percent:.2f}% – exiting optimizer loop", level="INFO")
                    break

            time.sleep(check_interval)
        except Exception as e:
            log(f"[ERROR] Micro-profit optimizer error for {symbol}: {e}", level="ERROR")
            break


def monitor_active_position(symbol, side, entry_price, initial_qty, start_time):
    """
    Real-time position management for active trades.
    Adjusts parameters based on price action and market conditions.

    Args:
        symbol: Trading pair symbol
        side: Position side (buy/sell)
        entry_price: Entry price
        initial_qty: Initial position quantity
        start_time: Trade start time
    """
    last_check_time = time.time()
    position_increased = False
    position_reduced = False

    while True:
        try:
            # Check if position still exists
            current_position = get_position_size(symbol)
            if current_position <= 0:
                log(f"{symbol} Position closed, ending dynamic position monitoring", level="DEBUG")
                break

            current_time = time.time()
            # Only check every 15 seconds to avoid excessive API calls
            if current_time - last_check_time < 15:
                time.sleep(0.5)
                continue

            last_check_time = current_time

            # Get current price and calculate profit
            price_data = safe_call_retry(exchange.fetch_ticker, symbol)
            if not price_data:
                log(f"Failed to fetch price for {symbol} during position monitoring", level="WARNING")
                time.sleep(5)
                continue

            current_price = price_data["last"]

            # Calculate profit percentage
            if side.lower() == "buy":
                profit_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                profit_percent = ((entry_price - current_price) / entry_price) * 100

            # Get current market conditions
            # We need to determine if momentum is increasing and volume is increasing
            try:
                ohlcv = fetch_ohlcv(symbol, timeframe="5m", limit=12)
                recent_closes = [c[4] for c in ohlcv[-6:]]
                recent_volumes = [c[5] for c in ohlcv[-6:]]

                # Check momentum direction
                momentum_increasing = False
                if side.lower() == "buy":
                    if recent_closes[-1] > recent_closes[-2] > recent_closes[-3]:
                        momentum_increasing = True
                else:
                    if recent_closes[-1] < recent_closes[-2] < recent_closes[-3]:
                        momentum_increasing = True

                # Check volume trend
                recent_avg_volume = sum(recent_volumes[-6:-1]) / 5  # Last 5 candles except current
                current_volume = recent_volumes[-1]
                volume_increasing = current_volume > recent_avg_volume * 1.2  # 20% higher volume
            except Exception as e:
                log(f"Error analyzing market data for {symbol}: {e}", level="ERROR")
                momentum_increasing = False
                volume_increasing = False

            # 1. Dynamic position sizing - add to winning position
            if profit_percent > 1.2 and momentum_increasing and volume_increasing and not position_increased:
                # Add to winning position (max 30% of initial size)
                additional_qty = initial_qty * 0.3

                # Check if we have margin for increase
                try:
                    # Calculate if we have enough margin
                    balance = get_cached_balance()
                    available_margin = balance * 0.92 - current_position * current_price * 0.5
                    additional_margin_needed = additional_qty * current_price * 0.2  # Assuming 5x leverage

                    if available_margin > additional_margin_needed:
                        # Execute the order
                        safe_call_retry(exchange.create_market_order, symbol, side.lower(), additional_qty)
                        position_increased = True
                        log(f"{symbol} 📈 Position increased by 30% due to strong momentum at +{profit_percent:.2f}%", level="INFO")
                        send_telegram_message(f"📈 Added to winning position {symbol} at +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error increasing position for {symbol}: {e}", level="ERROR")

            # 2. Dynamic profit taking - take partial profits if momentum weakens
            elif profit_percent > 0.6 and not momentum_increasing and not position_reduced:
                # Close part of position early if momentum weakens
                reduction_qty = current_position * 0.4  # Close 40% of current position

                try:
                    # Execute the partial close
                    safe_call_retry(exchange.create_market_order, symbol, "sell" if side.lower() == "buy" else "buy", reduction_qty, {"reduceOnly": True})
                    position_reduced = True
                    log(f"{symbol} 🔒 Partial profit taken (40%) at +{profit_percent:.2f}% due to weakening momentum", level="INFO")
                    send_telegram_message(f"🔒 Partial profit taken on {symbol} at +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error taking partial profits for {symbol}: {e}", level="ERROR")

            # 3. Dynamic TP adjustment - extend TP for strong momentum
            elif profit_percent > 1.8 and momentum_increasing:
                try:
                    # Look for TP2 orders
                    open_orders = exchange.fetch_open_orders(symbol)
                    tp_orders = [o for o in open_orders if o["type"].upper() == "LIMIT" and o["side"].upper() == ("SELL" if side.lower() == "buy" else "BUY")]

                    if tp_orders:
                        # Cancel existing TP order
                        for order in tp_orders:
                            exchange.cancel_order(order["id"], symbol)

                        # Calculate new extended TP price
                        new_tp_price = current_price * 1.007 if side.lower() == "buy" else current_price * 0.993

                        # Create new TP order
                        safe_call_retry(exchange.create_limit_order, symbol, "sell" if side.lower() == "buy" else "buy", current_position, new_tp_price, {"reduceOnly": True})

                        log(f"{symbol} 🎯 TP extended due to strong momentum at +{profit_percent:.2f}%", level="INFO")
                        send_telegram_message(f"🎯 Extended TP for {symbol} at +{profit_percent:.2f}%")
                except Exception as e:
                    log(f"Error adjusting TP for {symbol}: {e}", level="ERROR")

            time.sleep(1)  # Small delay to prevent excessive CPU usage

        except Exception as e:
            log(f"Error in position monitoring for {symbol}: {e}", level="ERROR")
            time.sleep(5)  # Longer delay on error


def check_micro_profit_exit(symbol, trade_data):
    """
    Automatically close trade if small profit percentage exceeds MICRO_PROFIT_THRESHOLD (in %)
    """
    if not MICRO_PROFIT_ENABLED or DRY_RUN:
        return

    try:
        ticker = safe_call_retry(exchange.fetch_ticker, symbol)
        if not ticker:
            return

        entry = trade_data.get("entry_price")
        side = trade_data.get("side")
        qty = trade_data.get("quantity")

        # Проверяем данные
        if not entry or not side or not qty or entry <= 0:
            log(f"[Micro-Profit] Invalid trade data for {symbol}: entry={entry}, side={side}, qty={qty}", level="WARNING")
            return

        current_price = ticker["last"]
        if current_price <= 0:
            log(f"[Micro-Profit] Invalid current price for {symbol}: {current_price}", level="WARNING")
            return

        if side.lower() == "buy":
            profit_percent = ((current_price - entry) / entry) * 100
            absolute_profit = (current_price - entry) * qty
        else:
            profit_percent = ((entry - current_price) / entry) * 100
            absolute_profit = (entry - current_price) * qty

        if profit_percent >= MICRO_PROFIT_THRESHOLD:
            log(f"{symbol} 💰 Micro-profit hit: +{profit_percent:.2f}% (+{absolute_profit:.2f} USDC) — closing early", level="INFO")
            send_telegram_message(f"💰 {symbol}: Early close on micro-profit +{profit_percent:.2f}% (+{absolute_profit:.2f} USDC)", force=True)
            safe_close_trade(exchange, symbol, trade_data, reason="micro_profit")

    except Exception as e:
        log(f"[Micro-Profit] Error for {symbol}: {e}", level="ERROR")


def check_stagnant_trade_exit(symbol, trade_data):
    """
    Exit trades that haven't moved beyond breakeven after timeout
    """
    try:
        open_time = trade_data.get("start_time")
        if not open_time or DRY_RUN:
            return

        elapsed_minutes = (datetime.utcnow() - open_time).total_seconds() / 60
        if elapsed_minutes >= MICRO_TRADE_TIMEOUT_MINUTES:
            log(f"{symbol} 💤 Trade stagnant for {elapsed_minutes:.1f} min — closing", level="INFO")
            send_telegram_message(f"💤 {symbol}: Stagnant trade auto-exit after {int(elapsed_minutes)}m", force=True)
            safe_close_trade(exchange, symbol, trade_data, reason="stagnant")
    except Exception as e:
        log(f"[Stagnant Exit] Error for {symbol}: {e}", level="ERROR")


def monitor_active_trades():
    """
    Periodically monitor open trades for micro-profit or timeout exit
    """
    while True:
        try:
            trades = trade_manager._trades.copy()
            for symbol, trade_data in trades.items():
                check_micro_profit_exit(symbol, trade_data)
                check_stagnant_trade_exit(symbol, trade_data)
        except Exception as e:
            log(f"[Monitor Trades] Error: {e}", level="ERROR")

        time.sleep(30)  # Adjust as needed


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
