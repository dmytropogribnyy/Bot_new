# core/engine_controller.py

import os
import threading
import time

import pandas as pd

from common.config_loader import (
    AGGRESSIVENESS_THRESHOLD,
    DRY_RUN,
    MICRO_PROFIT_ENABLED,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.entry_logger import log_entry
from core.exchange_init import exchange
from core.notifier import notify_dry_trade, notify_error
from core.risk_utils import get_max_positions
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, get_cached_positions, load_state, safe_call_retry, set_leverage_for_symbols
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()
last_balance = 0
MIN_SCORE_DELTA_SWITCH = 2
last_check_log_time = 0
last_balance_log_time = 0


def get_smart_switch_stats():
    """
    Calculate the success rate of previous smart switch operations.
    """
    try:
        if not os.path.exists("data/tp_performance.csv"):
            log(
                "[SmartSwitch] tp_performance.csv not found, skipping winrate calculation.",
                level="WARNING",
            )
            return 0.5

        df = pd.read_csv("data/tp_performance.csv", parse_dates=["Date"])
        recent = df[df["Result"] == "smart_switch"].tail(10)
        winrate = len(recent[recent["PnL (%)"] > 0]) / len(recent) if not recent.empty else 0
        return round(winrate, 2)
    except Exception as e:
        log(f"[SmartSwitch] Failed to calculate winrate: {e}", level="WARNING")
        return 0.5


def get_adaptive_switch_limit(balance, active_positions, recent_switch_winrate, aggressiveness_threshold):
    """
    Determine the maximum number of smart switches allowed based on
    account balance, current position count, and historical performance.
    """
    base_limit = 1 if balance < 50 else 2
    if active_positions == 0:
        base_limit += 1
    if get_aggressiveness_score() > aggressiveness_threshold:
        base_limit += 1
    if recent_switch_winrate > 0.7:
        base_limit += 1
    elif recent_switch_winrate < 0.3:
        base_limit -= 1
    return max(1, min(base_limit, 5))


def evaluate_position_quality(symbol, side, entry_price, current_price, duration_minutes, score=None):
    """
    Evaluate current position quality on a 0-10 scale.

    Args:
        symbol: Trading symbol
        side: Position side (buy/sell)
        entry_price: Entry price
        current_price: Current price
        duration_minutes: How long position has been open
        score: Original signal score (optional)

    Returns:
        float: Quality score from 1.0 to 10.0
    """
    # Calculate profit percentage
    if side.lower() == "buy":
        profit_percent = ((current_price - entry_price) / entry_price) * 100
    else:
        profit_percent = ((entry_price - current_price) / entry_price) * 100

    # Base score by profit
    if profit_percent <= -0.5:
        quality = 3.0  # Losing position
    elif profit_percent < 0:
        quality = 4.0  # Small loss
    elif profit_percent < 0.3:
        quality = 5.0  # Small profit
    elif profit_percent < 0.7:
        quality = 6.0  # Medium profit
    else:
        quality = 7.0  # Good profit

    # Time penalty
    if duration_minutes > 60:
        quality -= 1.5  # Significant penalty for long-held positions
    elif duration_minutes > 30:
        quality -= 0.8  # Moderate penalty

    # Original signal quality
    if score is not None:
        quality += (score - 3) * 0.5  # Adjust based on original signal quality

    return max(1.0, min(10.0, quality))


def should_switch_position(current_quality, new_score, balance, current_pnl=None):
    """
    Decide if we should close a current position for a new opportunity.
    Includes safeguards to prevent closing losing positions.

    Args:
        current_quality: Quality score of current position (0-10)
        new_score: Score of new trading signal (0-5)
        balance: Current account balance
        current_pnl: Current profit/loss percentage (optional)

    Returns:
        bool: True if switching is recommended, False otherwise
    """
    # Safeguard: Never switch out of a losing position
    if current_pnl is not None and current_pnl < 0:
        return False

    # Convert new score to quality scale
    new_quality = 5.0 + (new_score - 3) * 1.2

    # More aggressive switching for small accounts
    if balance < 150:
        switch_threshold = 1.8  # Lower threshold = more switching
    else:
        switch_threshold = 2.5

    return new_quality - current_quality >= switch_threshold


def run_trading_cycle(symbols, stop_event):
    """
    Process trading cycle with enhanced position quality evaluation and switching.
    """
    # Lazy imports to break circular dependencies
    from core.symbol_processor import process_symbol
    from core.trade_engine import (
        close_dry_trade,
        close_real_trade,
        enter_trade,
        get_position_size,
        safe_close_trade,
        trade_manager,
    )

    # Validate input
    if not symbols:
        log("No symbols provided to trading cycle", level="WARNING")
        return

    state = load_state()

    # Only set leverage when symbols change or on first run
    if not hasattr(run_trading_cycle, "last_symbols") or run_trading_cycle.last_symbols != symbols:
        log("Setting leverage for symbols due to symbol list change", level="DEBUG")
        set_leverage_for_symbols()
        run_trading_cycle.last_symbols = symbols.copy()  # Store a copy of the symbols

    # Adaptive risk and position management
    balance = get_cached_balance()
    max_positions = get_max_positions(balance)

    # Handle stopping flag
    if state.get("stopping"):
        open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
        log(f"Open trades count: {open_trades}", level="DEBUG")
        if open_trades == 0:
            log("All positions closed — stopping bot.", level="INFO")
            send_telegram_message("✅ All positions closed. Bot stopped.", force=True)
            if state.get("shutdown"):
                log("Shutdown flag detected — exiting fully.", level="INFO")
                os._exit(0)
        else:
            log(f"Waiting for {open_trades} open positions...", level="INFO")
        return

    # Main trading cycle
    # Efficiently check position count once
    positions = get_cached_positions()
    active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)

    # Check against max_positions before processing
    if active_positions >= max_positions:
        log(f"Max positions ({max_positions}) reached. Active: {active_positions}. Skipping cycle.", level="INFO")
        return

    # Evaluate current positions for potential switching
    current_positions = []
    if MICRO_PROFIT_ENABLED:  # Use same flag for position quality evaluation
        for sym in symbols:
            trade_data = trade_manager.get_trade(sym)
            if trade_data:
                try:
                    current_price = safe_call_retry(exchange.fetch_ticker, sym)["last"]
                    duration_minutes = int((time.time() - trade_data["start_time"].timestamp()) / 60)

                    # Calculate current P&L
                    side = trade_data["side"]
                    entry = trade_data["entry"]
                    if side.lower() == "buy":
                        current_pnl = ((current_price - entry) / entry) * 100
                    else:
                        current_pnl = ((entry - current_price) / entry) * 100

                    quality = evaluate_position_quality(sym, side, entry, current_price, duration_minutes, trade_data.get("score"))

                    current_positions.append({"symbol": sym, "quality": quality, "duration": duration_minutes, "pnl": current_pnl})

                    log(f"{sym} Position quality: {quality:.1f}/10 (duration: {duration_minutes} min, PnL: {current_pnl:.2f}%)", level="DEBUG")
                except Exception as e:
                    log(f"Error evaluating position {sym}: {e}", level="ERROR")

    recent_wr = get_smart_switch_stats()
    switch_limit = get_adaptive_switch_limit(balance, active_positions, recent_wr, AGGRESSIVENESS_THRESHOLD)
    smart_switch_count = 0

    for symbol in symbols:
        if stop_event.is_set():
            log(f"[Trading Cycle] Stop signal received, aborting cycle for {symbol}.", level="INFO")
            break

        # Skip if max positions reached during iteration
        positions = get_cached_positions()
        current_active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)
        if current_active_positions >= max_positions:
            log(f"Max positions ({max_positions}) reached during cycle. Skipping remaining symbols.", level="INFO")
            break

        try:
            log(f"🔍 Checking {symbol}", level="DEBUG")

            trade_data = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade_data:
                continue

            score = trade_data["score"]
            is_reentry = trade_data["is_reentry"]

            # Check if we should switch positions
            if MICRO_PROFIT_ENABLED and current_positions and score > 3.5:  # Only consider good signals
                for pos in current_positions:
                    if should_switch_position(pos["quality"], score, balance, pos["pnl"]):
                        log(f"🔄 Switching {pos['symbol']} (quality: {pos['quality']:.1f}) for better opportunity {symbol} (score: {score:.1f})", level="INFO")
                        send_telegram_message(f"🔄 Switching from {pos['symbol']} to {symbol} for better opportunity", force=True)

                        # Correctly close position with safe_close_trade
                        pos_trade_data = trade_manager.get_trade(pos["symbol"])
                        if pos_trade_data:
                            safe_close_trade(exchange, pos["symbol"], pos_trade_data)

                        # Remove from list to avoid closing multiple positions
                        current_positions = [p for p in current_positions if p["symbol"] != pos["symbol"]]
                        break

            # Smart switch logic for same symbol
            current_trade = trade_manager.get_trade(symbol)
            if current_trade:
                current_score = current_trade.get("score", 0)
                if score - current_score >= MIN_SCORE_DELTA_SWITCH:
                    if smart_switch_count < switch_limit:
                        log(
                            f"🧠 Smart Switch: {symbol} ({current_score}→{score})",
                            level="INFO",
                        )
                        send_telegram_message(
                            f"🔄 *Smart Switch* `{symbol}`: {current_score}→{score}",
                            force=True,
                            parse_mode="MarkdownV2",
                        )
                        if DRY_RUN:
                            close_dry_trade(symbol)
                        else:
                            close_real_trade(symbol)
                        smart_switch_count += 1
                        is_reentry = True
                        time.sleep(1)
                    else:
                        log(
                            f"⚠️ Smart Switch skipped for {symbol} — limit reached ({switch_limit})",
                            level="WARNING",
                        )
                        continue
                else:
                    continue

            # Enter trade
            if DRY_RUN:
                notify_dry_trade(trade_data)
                log_entry(trade_data, status="SUCCESS", mode="DRY_RUN")
            enter_trade(
                trade_data["symbol"],
                trade_data["direction"],
                trade_data["qty"],
                trade_data["score"],
                is_reentry,
            )
            if not DRY_RUN:
                log_entry(trade_data, status="SUCCESS", mode="REAL_RUN")

        except Exception as e:
            notify_error(f"🔥 Error during {symbol}: {str(e)}")
            log(f"Error in trading cycle for {symbol}: {e}", level="ERROR")
