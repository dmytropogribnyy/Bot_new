# telegram_commands.py
"""
Telegram command handlers for BinanceBot
Processes user commands and provides bot control
"""

import json
import os
import threading
import time
from threading import Lock, Thread

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH, LEVERAGE_MAP
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.trade_engine import close_real_trade, trade_manager
from main import stop_event
from missed_tracker import flush_best_missed_opportunities
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from symbol_activity_tracker import get_most_active_symbols
from telegram.telegram_ip_commands import handle_ip_and_misc_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, get_runtime_config, load_state, save_state
from utils_logging import log

command_lock = Lock()


# --- Helpers ------------------------------------------------------------
def _format_pos_real(p):
    """
    Format real position for Telegram display with enhanced error handling
    """
    try:
        symbol = escape_markdown_v2(p.get("symbol", ""))
        qty = float(p.get("contracts", 0))
        entry = float(p.get("entryPrice", 0))
        side = p.get("side", "").upper()
        leverage = int(p.get("leverage", LEVERAGE_MAP.get(p.get("symbol", ""), 1))) or 1
        if not qty or not entry:
            return f"{symbol} ({side}, 0.000) @ 0.00 = ~0.00 USDC (Leverage: {leverage}x, Margin: ~0.00 USDC)"
        notional = qty * entry
        margin = notional / leverage
        return f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} = ~{notional:.2f} USDC " f"(Leverage: {leverage}x, Margin: ~{margin:.2f} USDC)"
    except Exception as e:
        log(f"Error formatting position: {e}", level="ERROR")
        return f"{p.get('symbol', 'Unknown')} (Error formatting)"


def _format_pos_dry(t):
    """
    Format dry-run position for Telegram display with enhanced error handling
    """
    try:
        symbol = escape_markdown_v2(t.get("symbol", ""))
        side = t.get("side", "").upper()
        qty = float(t.get("qty", 0))
        entry = float(t.get("entry", 0))
        leverage = LEVERAGE_MAP.get(t.get("symbol", ""), 5)
        if not qty or not entry:
            return f"{symbol} ({side}, 0.000) @ 0.00 = ~0.00 USDC (Leverage: {leverage}x, Margin: ~0.00 USDC)"
        notional = qty * entry
        margin = notional / leverage
        return f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} = ~{notional:.2f} USDC " f"(Leverage: {leverage}x, Margin: ~{margin:.2f} USDC)"
    except Exception as e:
        log(f"Error formatting dry position: {e}", level="ERROR")
        return f"{t.get('symbol', 'Unknown')} (Error formatting)"


def _monitor_stop_timeout(reason, state, timeout_minutes=30):
    """
    Monitor stop process with timeout warning and improved cleanup
    """
    start = time.time()
    check_interval = 60  # 60 seconds between checks
    last_notification_time = 0  # Track last notification time
    notification_interval = 30  # Only send updates every 30 seconds

    while state.get("stopping") and time.time() - start < timeout_minutes * 60:
        try:
            # Check if positions are closed
            if DRY_RUN:
                open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
            else:
                from core.binance_api import get_open_positions

                positions = get_open_positions()
                open_details = [_format_pos_real(p) for p in positions]

                # Actively try to close positions again if still open after 5 minutes
                if open_details and time.time() - start > 300:  # 5 minutes
                    for pos in positions:
                        if float(pos.get("contracts", 0)) > 0:
                            try:
                                close_real_trade(pos["symbol"])
                                log(f"[Stop] Retry closing position for {pos['symbol']}", level="INFO")
                            except Exception as e:
                                log(f"[Stop] Failed to close position: {e}", level="ERROR")

            current_time = time.time()
            if current_time - last_notification_time >= notification_interval:
                # Handle timeout warning with throttled notifications
                if time.time() - start >= timeout_minutes * 60:
                    if open_details:
                        msg = (
                            "⏰ *Stop timeout warning*.\n"
                            f"{len(open_details)} positions still open after {int((time.time() - start) // 60)} minutes:\n" + "\n".join(open_details) + "\nUse /panic YES to force close."
                        )
                        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                        log(
                            f"[Stop] Timeout warning sent after {int((time.time() - start) // 60)} minutes",
                            level="INFO",
                        )
                    else:
                        send_telegram_message(
                            f"🛑 *{reason}*.\nAll positions closed. Bot will exit shortly.",
                            force=True,
                            parse_mode="MarkdownV2",
                        )
                        state["stopping"] = False
                        save_state(state)
                        break
                elif open_details:
                    # Simplified message for regular updates
                    symbols = [p.split("(")[0].strip() for p in open_details]
                    msg = f"⏳ Still waiting on {len(open_details)} positions: {', '.join(symbols)}"
                    send_telegram_message(msg, force=True)

                # Update notification timestamp
                last_notification_time = current_time

        except Exception as e:
            log(f"[Stop Monitor] Error: {e}", level="ERROR")

        time.sleep(check_interval)

    # Check one final time if all positions are closed
    try:
        if not DRY_RUN:
            from core.binance_api import get_open_positions

            positions = get_open_positions()
            if not any(float(p.get("contracts", 0)) > 0 for p in positions):
                send_telegram_message("✅ All positions closed.", force=True)
                state["stopping"] = False
                save_state(state)
                log("[Stop Monitor] All positions successfully closed", level="INFO", important=True)
    except Exception as e:
        log(f"[Stop Monitor] Final check error: {e}", level="ERROR")


def _initiate_stop(reason):
    """
    Initiate stop process with enhanced position handling
    """
    # Import the global stop_event
    from main import stop_event

    state = load_state()
    if state.get("stopping"):
        send_telegram_message("⚠️ Bot is already stopping…", force=True)
        return False

    state["stopping"] = True
    save_state(state)

    # Set the global stop event
    if stop_event:
        stop_event.set()
        log(f"[Stop] Setting global stop_event for {reason}", level="INFO")

    try:
        if DRY_RUN:
            open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            positions = exchange.fetch_positions()
            open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

            # Actively close positions in real mode
            for pos in positions:
                if float(pos.get("contracts", 0)) > 0:
                    try:
                        close_real_trade(pos["symbol"])
                        log(f"[Stop] Closing position for {pos['symbol']}", level="INFO")
                    except Exception as e:
                        log(f"[Stop] Failed to close position: {e}", level="ERROR")
    except Exception as e:
        log(f"[Stop] Failed to fetch positions: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
        open_details = []

    if open_details:
        msg = f"🛑 *{escape_markdown_v2(reason)}*.\n" "Waiting for these positions to close:\n" + "\n".join(open_details) + "\nNo new trades will be opened."
        Thread(target=_monitor_stop_timeout, args=(reason, state), daemon=True).start()
    else:
        msg = f"🛑 {reason}.\nNo open positions. Bot will stop shortly."

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log(f"[Stop] {reason}", level="INFO")
    return True


# --- Command Handlers ---------------------------------------------------
def handle_goals_command():
    """
    Show progress towards daily/weekly profit goals
    """
    try:
        from common.config_loader import DAILY_PROFIT_TARGET, WEEKLY_PROFIT_TARGET

        # Fetch today's and week's profit from stats
        from stats import get_trades_for_past_days

        today_trades = get_trades_for_past_days(1)
        today_profit = today_trades["PnL (%)"].sum() if not today_trades.empty else 0
        week_trades = get_trades_for_past_days(7)
        week_profit = week_trades["PnL (%)"].sum() if not week_trades.empty else 0

        # Calculate progress
        daily_progress = (today_profit / DAILY_PROFIT_TARGET) * 100 if DAILY_PROFIT_TARGET else 0
        weekly_progress = (week_profit / WEEKLY_PROFIT_TARGET) * 100 if WEEKLY_PROFIT_TARGET else 0

        msg = (
            f"🎯 *Profit Goals Progress*\n"
            f"Daily Target: {DAILY_PROFIT_TARGET:.2f} USDC\n"
            f"Today's Profit: {today_profit:.2f} USDC ({daily_progress:.1f}%)\n"
            f"Weekly Target: {WEEKLY_PROFIT_TARGET:.2f} USDC\n"
            f"This Week's Profit: {week_profit:.2f} USDC ({weekly_progress:.1f}%)"
        )
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("Sent profit goals progress via /goals command.", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to fetch goals: {e}", force=True)
        log(f"Goals command error: {e}", level="ERROR")


def handle_risk_command(message):
    """
    Adjust risk level (e.g., /risk 0.02)
    """
    try:
        from core.risk_utils import get_max_risk, set_max_risk

        parts = message.get("text", "").strip().split()
        if len(parts) == 1:
            current_risk = get_max_risk()
            msg = f"Current Risk Level: {current_risk*100:.1f}%\n" "Use /risk <value> to set new risk (e.g., /risk 0.02 for 2%)"
            send_telegram_message(msg, force=True)
        else:
            new_risk = float(parts[1])
            if new_risk < 0.01 or new_risk > 0.05:
                send_telegram_message("❌ Risk must be between 0.01 (1%) and 0.05 (5%)", force=True)
            else:
                set_max_risk(new_risk)
                send_telegram_message(f"✅ Risk level set to {new_risk*100:.1f}%", force=True)
                log(f"Risk level set to {new_risk*100:.1f}% via /risk command", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to set risk: {e}", force=True)
        log(f"Risk command error: {e}", level="ERROR")


def handle_status_command(state):
    """
    Report current bot status: running/stopping, DRY_RUN, active positions, balance
    """
    try:
        mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
        stopping = state.get("stopping", False)
        msg = f"🔍 *Bot Status*\nMode: `{mode}`\nStopping: `{stopping}`"

        if DRY_RUN:
            open_trades = [_format_pos_dry(t) for t in trade_manager._trades.values()]
        else:
            positions = exchange.fetch_positions()
            open_trades = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

        msg += f"\nOpen Positions: `{len(open_trades)}`"
        if open_trades:
            msg += "\n" + "\n".join(open_trades)

        balance = round(float(get_cached_balance()), 2)
        msg += f"\nBalance: `{balance}` USDC"

        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("Sent bot status via /status", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to get bot status: {e}", force=True)
        log(f"Status command error: {e}", level="ERROR")


def handle_filters_command(message):
    """
    Adjust pair filters (e.g., /filters 0.19 16000)
    """
    try:
        from common.config_loader import set_filter_thresholds

        parts = message.get("text", "").strip().split()
        if len(parts) == 1:
            try:
                with open("data/filter_settings.json", "r") as f:
                    filters = json.load(f)
                msg = f"Current Filters:\nATR: {filters['atr_percent']*100:.2f}%\nVolume: {filters['volume_usdc']:,.0f} USDC\n" "Use /filters <atr_percent> <volume_usdc> to set new filters"
            except Exception:
                msg = "No filters set. Use /filters <atr_percent> <volume_usdc> to set new filters"
            send_telegram_message(msg, force=True)
        else:
            atr_percent = float(parts[1])
            volume_usdc = float(parts[2])
            set_filter_thresholds(atr_percent, volume_usdc)
            send_telegram_message(f"✅ Filters updated: ATR={atr_percent*100:.2f}%, Volume={volume_usdc:,.0f} USDC", force=True)
            log(f"Filters updated via /filters command: ATR={atr_percent*100:.2f}%, Volume={volume_usdc:,.0f} USDC", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to set filters: {e}", force=True)
        log(f"Filters command error: {e}", level="ERROR")


def handle_stop_command():
    """
    Enhanced stop command with active position closing and stop_event triggering
    """
    # Import the global stop_event
    from main import stop_event

    # Make sure we load the latest state
    state = load_state()
    log(f"[Stop] Current state before update: stopping={state.get('stopping', False)}", level="DEBUG")

    # Update the stopping flag and save immediately
    state["stopping"] = True
    save_state(state)
    log("[Stop] Updated state file with stopping=True", level="INFO")

    # Verify state was saved correctly
    verification_state = load_state()
    log(f"[Stop] Verified state after update: stopping={verification_state.get('stopping', False)}", level="DEBUG")

    # Set the global stop event
    if stop_event:
        stop_event.set()
        log("[Stop] Setting global stop_event for stop command", level="INFO", important=True)

    try:
        if DRY_RUN:
            open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            # Use our new function to get actual exchange positions
            from core.binance_api import get_open_positions

            positions = get_open_positions()
            open_details = [_format_pos_real(p) for p in positions]

            # Actively close positions in real mode
            for pos in positions:
                if float(pos.get("contracts", 0)) > 0:
                    try:
                        close_real_trade(pos["symbol"])
                        log(f"[Stop] Closing position for {pos['symbol']}", level="INFO")
                    except Exception as e:
                        log(f"[Stop] Failed to close position: {e}", level="ERROR")
    except Exception as e:
        log(f"[Stop] Failed to fetch positions: {e}", level="ERROR")
        send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
        open_details = []

    if open_details:
        msg = "🛑 *Stop command received*.\n" "Closing the following positions:\n" + "\n".join(open_details) + "\nNo new trades will be opened."
        Thread(target=_monitor_stop_timeout, args=("Stop command", state), daemon=True).start()
    else:
        msg = "🛑 *Stop command received*.\nNo open positions. Bot will stop shortly."
        # Note: We're NOT resetting stopping flag here - let the main loop handle shutdown
        log("[Stop] No open positions. Bot will stop shortly.", level="INFO")

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log("[Stop] Stop command processed.", level="INFO")


def handle_panic(message, state):
    """
    Emergency force closure of all positions and orders with timeout
    """
    # Log panic initiation
    log("[Panic] Panic command received! Forcing closure of all positions and orders.", level="WARNING", important=True)

    # Set stopping flag
    state["stopping"] = True
    state["panic_mode"] = True  # Add special panic flag
    save_state(state)

    # Set stop event
    if stop_event:
        stop_event.set()

    send_telegram_message("🚨 PANIC MODE ACTIVATED! Forcing immediate closure of all positions...", force=True)

    # Set a hard exit timeout (force exit after 30 seconds)
    def force_exit():
        log("[Panic] Timeout reached - forcing exit", level="WARNING", important=True)
        send_telegram_message("⚠️ Panic timeout reached - forcing exit", force=True)
        os._exit(1)

    # Start the timeout timer
    timeout_timer = threading.Timer(30, force_exit)
    timeout_timer.daemon = True
    timeout_timer.start()

    try:
        # Get ALL positions directly from exchange
        positions = exchange.fetch_positions()
        active_positions = [p for p in positions if float(p.get("contracts", 0)) > 0]

        if not active_positions:
            log("[Panic] No active positions found", level="INFO")
            send_telegram_message("✅ No active positions found", force=True)
            # Cancel the timeout
            timeout_timer.cancel()
            os._exit(0)
            return

        # Log active positions
        symbols = [p["symbol"] for p in active_positions]
        log(f"[Panic] Found {len(active_positions)} active positions: {', '.join(symbols)}", level="INFO")

        # First attempt: cancel all orders for all symbols
        for symbol in set(symbols):
            try:
                # Cancel all orders
                exchange.futures_cancel_all_open_orders(symbol=symbol.replace("/", ""))
                log(f"[Panic] Cancelled all orders for {symbol}", level="INFO")
            except Exception as e:
                log(f"[Panic] Failed to cancel orders for {symbol}: {e}", level="ERROR")

        # Second attempt: force close all positions with market orders
        for position in active_positions:
            symbol = position["symbol"]
            side = "sell" if position["side"] == "long" else "buy"
            qty = float(position["contracts"])

            try:
                # Force market order with reduceOnly
                exchange.create_market_order(symbol, side, qty, params={"reduceOnly": True})
                log(f"[Panic] Force closed position for {symbol}: {qty} {position['side']}", level="INFO")
            except Exception as e:
                log(f"[Panic] Failed to close position for {symbol}: {e}", level="ERROR")
                send_telegram_message(f"⚠️ Failed to close {symbol}: {e}", force=True)

        # Final verification
        positions = exchange.fetch_positions()
        remaining = [p for p in positions if float(p.get("contracts", 0)) > 0]

        if remaining:
            remaining_symbols = [p["symbol"] for p in remaining]
            log(f"[Panic] {len(remaining)} positions still open after panic: {', '.join(remaining_symbols)}", level="WARNING")
            send_telegram_message(f"⚠️ {len(remaining)} positions still open after panic. Force exiting.", force=True)
        else:
            log("[Panic] All positions successfully closed", level="INFO")
            send_telegram_message("✅ All positions closed successfully. Force exiting.", force=True)

        # Cancel the timeout since we're done
        timeout_timer.cancel()

        # Clean exit
        os._exit(0)

    except Exception as e:
        log(f"[Panic] Critical error during panic: {e}", level="ERROR")
        send_telegram_message(f"❌ Critical error during panic: {e}", force=True)
        # Don't cancel timeout - let it force exit


# -----------------------------------------------------------------------
def handle_shutdown(message, state):
    """
    Gracefully shutdown bot with proper position and order closure
    """
    # Import necessary components
    import common.config_loader as config_loader

    # Log shutdown initiation
    log("[Shutdown] Shutdown command received. Initiating shutdown process...", level="INFO", important=True)

    config_loader.RUNNING = False

    state["shutdown"] = True
    state["stopping"] = True
    save_state(state)

    # Set the global stop event
    if stop_event:
        stop_event.set()
        log("[Shutdown] Setting global stop_event for shutdown command", level="INFO", important=True)

    try:
        # Get all symbols with active positions
        active_symbols = set()
        try:
            positions = exchange.fetch_positions()
            for pos in positions:
                if float(pos.get("contracts", 0)) > 0:
                    active_symbols.add(pos["symbol"])
        except Exception as e:
            log(f"[Shutdown] Failed to fetch positions: {e}", level="ERROR")
            # Fallback to trade manager symbols
            active_symbols = set(trade_manager._trades.keys())

        if DRY_RUN:
            open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            positions = exchange.fetch_positions()
            open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

            # Actively close positions in real mode
            for pos in positions:
                if float(pos.get("contracts", 0)) > 0:
                    try:
                        close_real_trade(pos["symbol"])
                        log(f"[Shutdown] Closing position for {pos['symbol']}", level="INFO")
                    except Exception as e:
                        log(f"[Shutdown] Failed to close position: {e}", level="ERROR")

        if open_details:
            msg = "🛑 *Shutdown initiated*.\n" "Waiting for these positions to close:\n" + "\n".join(open_details) + "\nBot will exit after closure."
            Thread(target=_monitor_stop_timeout, args=("Shutdown", state, 15), daemon=True).start()
        else:
            msg = "🛑 *Shutdown initiated*.\nNo open positions. Bot will exit shortly."
            # No positions to close, can exit immediately
            log("[Shutdown] No open positions - exiting immediately", level="INFO", important=True)
            send_telegram_message("✅ Shutdown complete. No open trades. Exiting...", force=True)
            os._exit(0)

        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("[Shutdown] Shutdown process in progress - waiting for positions to close", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to initiate shutdown: {e}", force=True)
        log(f"Shutdown error: {e}", level="ERROR")


def handle_runtime_command():
    try:
        config = get_runtime_config()
        if not config:
            send_telegram_message("⚠️ Runtime config is empty or not found.", force=True)
            return

        msg = "⚙️ *Current Runtime Config:*\n"
        for key, value in config.items():
            msg += f"`{key}`: *{value}*\n"

        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    except Exception as e:
        send_telegram_message(f"❌ Error fetching runtime config: {e}", force=True)


def handle_open_command(state):
    """
    Show all open positions (DRY or REAL) with potential TP1/TP2 profit
    """
    try:
        from core.strategy import calculate_tp_targets
        from utils_core import get_cached_balance

        balance = float(get_cached_balance())
        tp1_total, tp2_total = 0.0, 0.0

        if DRY_RUN:
            open_list = []
            trades = [t for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
            for t in trades:
                symbol = t["symbol"]
                qty = float(t["qty"])
                entry = float(t["entry"])
                side = t["side"].lower()

                tp1, tp2 = calculate_tp_targets(symbol, side, entry)

                profit1 = (tp1 - entry) * qty if side == "buy" else (entry - tp1) * qty
                profit2 = (tp2 - entry) * qty if side == "buy" else (entry - tp2) * qty
                tp1_total += profit1
                tp2_total += profit2

                pos_str = _format_pos_dry(t)
                open_list.append(f"{pos_str}\n→ TP1: +{profit1:.2f} | TP2: +{profit2:.2f} USDC")

            header = "🔍 *Open DRY positions:*"
        else:
            open_list = []
            positions = exchange.fetch_positions()
            real_positions = [p for p in positions if float(p.get("contracts", 0)) > 0]
            for p in real_positions:
                symbol = p["symbol"]
                qty = float(p["contracts"])
                entry = float(p["entryPrice"])
                side = p["side"].lower()

                tp1, tp2 = calculate_tp_targets(symbol, side, entry)

                profit1 = (tp1 - entry) * qty if side == "buy" else (entry - tp1) * qty
                profit2 = (tp2 - entry) * qty if side == "buy" else (entry - tp2) * qty
                tp1_total += profit1
                tp2_total += profit2

                pos_str = _format_pos_real(p)
                open_list.append(f"{pos_str}\n→ TP1: +{profit1:.2f} | TP2: +{profit2:.2f} USDC")

            header = "🔍 *Open positions:*"

        if not open_list:
            send_telegram_message(f"{header} none.", force=True)
        else:
            msg = (
                f"{header}\n\n" + "\n\n".join(open_list) + f"\n\n📊 *Total TP1:* {tp1_total:.2f} USDC ({tp1_total / balance * 100:.2f}%)\n"
                f"🏆 *Total TP2:* {tp2_total:.2f} USDC ({tp2_total / balance * 100:.2f}%)"
            )
            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

        log("Sent /open positions with potential PnL.", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to fetch open positions: {e}", force=True)
        log(f"Open positions error: {e}", level="ERROR")


def handle_telegram_command(message, state):
    """
    Main Telegram command handler with thread safety and enhanced reliability
    """
    # Get message timestamp (Telegram provides this in UTC seconds)
    message_date = message.get("date", 0)
    session_start_time = state.get("session_start_time", 0)

    # Skip commands sent before current session started
    if message_date and session_start_time and message_date < session_start_time:
        log(f"Ignoring stale command from previous session: {message.get('text', '').strip()}", level="DEBUG")
        return
    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id", 0)
    log(f"Received command: {text} from chat ID {chat_id}", level="DEBUG")

    if "last_command" not in state:
        state["last_command"] = None

    with command_lock:  # Thread-safe command processing
        if text in [
            "/router_reboot",
            "/cancel_reboot",
            "/ipstatus",
            "/forceipcheck",
            "/pairstoday",
            "/debuglog",
            "/log",
            "/runtime",
            "/signalblocks",
            "/reasons",
        ] or text.startswith("/close_dry"):
            handle_ip_and_misc_commands(text, _initiate_stop)
            return
        elif text == "/goals":
            handle_goals_command()
        elif text.startswith("/risk"):
            handle_risk_command(message)
        elif text.startswith("/filters"):
            handle_filters_command(message)
        elif text == "/help":
            help_msg = (
                "🤖 Available Commands:\n\n"
                "💰 /balance - Show current USDC balance\n"
                "❌ /cancel_reboot - Cancel router reboot mode\n"
                "⛔ /cancel_stop - Cancel stop process if pending\n"
                "🔒 /close_dry - Close a DRY position (e.g., /close_dry BTC/USDC)\n"
                "🧾 /debuglog - Show last 50 logs (DRY_RUN only)\n"
                "📡 /forceipcheck - Force immediate IP check\n"
                "🎯 /goals - Show progress towards daily/weekly profit goals\n"
                "📊 /heatmap - Generate 7-day score heatmap\n"
                "📖 /help - Show this message\n"
                "🌐 /ipstatus - Show current/previous IP + router mode\n"
                "📉 /last - Show last closed trade\n"
                "📜 /log - Export today's log to Telegram\n"
                "⚖️ /mode - Show strategy bias and score\n"
                "📈 /open - Show open positions\n"
                "🔄 /restart - Restart bot after closing positions\n"
                "⚠️ /risk - Adjust risk level (e.g., /risk 0.02)\n"
                "🔄 /router_reboot - Plan router reboot\n"
                "▶️ /resume_after_ip - Resume after IP change\n"
                "🚪 /shutdown - Exit bot after positions close\n"
                "🛑 /stop - Stop after all positions close\n"
                "🚨 /panic - Force close all trades (confirmation)\n"
                "🔍 /status - Show bot status\n"
                "📊 /summary - Show performance summary\n"
                "⚙️ /filters - Adjust pair filters (e.g., /filters 0.19 16000)\n"
                "🔧 /runtime - Show current runtime config\n"
                "🧱 /signalblocks - Show blocked signals (if any)\n"
                "❌ /reasons - Show signal rejection reasons\n"
                "📈 /pairstoday - Show today's selected pairs"
                "🧠 /runtime - Show current runtime config (risk, score, etc)"
            )

            send_telegram_message(help_msg, force=True, parse_mode="")
            log("Sent help message.", level="INFO")
        elif text == "/summary":
            try:
                summary = generate_summary()
                if DRY_RUN:
                    open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
                else:
                    positions = exchange.fetch_positions()
                    open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]
                msg = summary + "\n\n*Open Positions*:\n" + ("\n".join(open_details) if open_details else "None")
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent summary via /summary.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to generate summary: {e}", force=True)
                log(f"Summary error: {e}", level="ERROR")
        elif text == "/heatmap":
            if DRY_RUN:
                send_telegram_message("Heatmap unavailable in DRY_RUN mode.", force=True)
            else:
                try:
                    generate_score_heatmap(days=7)
                    log("Generated heatmap.", level="INFO")
                except Exception as e:
                    send_telegram_message(f"❌ Failed to generate heatmap: {e}", force=True)
                    log(f"Heatmap error: {e}", level="ERROR")
        elif text == "/stop":
            handle_stop_command()
        elif text in ("/panic", "yes"):
            handle_panic(message, state)
        elif text == "/shutdown":
            handle_shutdown(message, state)
        elif text == "/status":
            handle_status_command(state)
        elif text == "/resume_after_ip":
            state = load_state()
            if DRY_RUN:
                if state.get("stopping"):
                    state["stopping"] = False
                    save_state(state)
                    send_telegram_message("✅ DRY_RUN resumed after IP change.", force=True)
                else:
                    send_telegram_message("DRY_RUN: Bot already running.", force=True)
                return
            if not state.get("stopping"):
                send_telegram_message("ℹ️ Bot already running.", force=True)
                return
            state["stopping"] = False
            save_state(state)
            send_telegram_message("✅ Resumed after IP change.", force=True)
            log("Resumed after IP change.", level="INFO")
        elif text == "/mode":
            try:
                score = round(get_aggressiveness_score(), 2)
                bias = "🔥 HIGH" if score >= 3.5 else "⚡ MODERATE" if score >= 2.5 else "🧊 LOW"
                msg = f"🎯 *Strategy Bias*: {bias}\n📈 *Score*: `{score}`"
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent mode info.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to fetch mode: {e}", force=True)
                log(f"Mode error: {e}", level="ERROR")
        elif text == "/open":
            handle_open_command(state)
        elif text == "/last":
            try:
                df = pd.read_csv(EXPORT_PATH)
                if df.empty:
                    send_telegram_message("No trades logged yet.", force=True)
                else:
                    last = df.iloc[-1]

                    # Include commission if available
                    commission_info = ""
                    if "Commission" in last:
                        commission_info = f"\nCommission: {round(last['Commission'], 5)} USDC"

                    msg = (
                        f"{'[DRY_RUN]\n' if DRY_RUN else ''}Last Trade:\n"
                        f"{last['Symbol']} - {last['Side']}@{round(last['Entry Price'],4)} -> {round(last['Exit Price'],4)}\n"
                        f"PnL: {round(last['PnL (%)'],2)}% ({last['Result']}){commission_info}"
                    )
                    send_telegram_message(msg, force=True)
                log("Sent last trade info.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to read last trade: {e}", force=True)
                log(f"Last trade error: {e}", level="ERROR")
        elif text == "/balance":
            try:
                balance = round(float(get_cached_balance()), 2)
                send_telegram_message(f"💰 Balance: {balance} USDC", force=True)
                log("Sent balance info.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to fetch balance: {e}", force=True)
                log(f"Balance error: {e}", level="ERROR")
        elif text == "/hot":
            top = get_most_active_symbols(top_n=5)
            msg = "*Top 5 Active Symbols (Last Hour):*\n" + "\n".join(f"- {s}" for s in top)
            send_telegram_message(msg)

        elif text == "/missedlog":
            flush_best_missed_opportunities(top_n=5)

        elif text == "/signalconfig":
            config = get_runtime_config()

            msg = "*Current Adaptive Signal Config:*\n" + "\n".join(f"`{k}` = `{v}`" for k, v in config.items())
            send_telegram_message(msg)

        elif text == "/runtime":
            handle_runtime_command()
            log("Handled /runtime command.", level="INFO")

        elif text == "/restart":
            state["stopping"] = True
            state["restart_pending"] = True
            save_state(state)

            try:
                if DRY_RUN:
                    open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]

                    # For DRY_RUN, just restart immediately
                    msg = "🔄 *Restarting bot in DRY_RUN mode*.\n" + "Bot will restart shortly."
                    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                    log("Restart command received in DRY_RUN mode.", level="INFO")

                    # System call for more reliable restart
                    try:
                        os.system("python main.py")  # Launch new instance
                        os._exit(0)  # Exit cleanly after launching
                    except Exception as e:
                        log(f"Restart system call error: {e}", level="ERROR")
                        send_telegram_message(f"❌ Restart system call failed: {e}", force=True)
                else:
                    positions = exchange.fetch_positions()
                    open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

                    # Close positions first in real mode
                    for pos in positions:
                        if float(pos.get("contracts", 0)) > 0:
                            try:
                                close_real_trade(pos["symbol"])
                                log(f"[Restart] Closing position for {pos['symbol']}", level="INFO")
                            except Exception as e:
                                log(f"[Restart] Failed to close position: {e}", level="ERROR")

                    msg = "🔄 *Restarting bot*.\n" + (f"Closing positions:\n{'\n'.join(open_details)}\n" if open_details else "No open positions.\n") + "Bot will restart shortly."
                    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                    log("Restart command received.", level="INFO")

                    # Monitor for actual restart when positions are closed
                    def monitor_restart():
                        start_time = time.time()
                        max_wait = 300  # 5 minutes max wait

                        while time.time() - start_time < max_wait:
                            try:
                                positions = exchange.fetch_positions()
                                if not any(float(p.get("contracts", 0)) > 0 for p in positions):
                                    log("All positions closed - restarting bot", level="INFO")
                                    send_telegram_message("✅ All positions closed - restarting now", force=True)

                                    # System call for more reliable restart
                                    try:
                                        os.system("python main.py")  # Launch new instance
                                        os._exit(0)  # Exit cleanly after launching
                                    except Exception as e:
                                        log(f"Restart system call error: {e}", level="ERROR")
                                        send_telegram_message(f"❌ Restart system call failed: {e}", force=True)
                                    return
                            except Exception as e:
                                log(f"Error in restart monitor: {e}", level="ERROR")

                            time.sleep(10)  # Check every 10 seconds

                        # Timeout reached
                        log("Restart timeout - forcing restart", level="WARNING")
                        send_telegram_message("⚠️ Restart timeout - forcing restart anyway", force=True)

                        try:
                            os.system("python main.py")
                            os._exit(0)
                        except Exception as e:
                            log(f"Forced restart error: {e}", level="ERROR")

                    # Start monitor thread
                    Thread(target=monitor_restart, daemon=True).start()
            except Exception as e:
                state["stopping"] = False
                state["restart_pending"] = False
                save_state(state)
                send_telegram_message(f"❌ Restart failed: {e}", force=True)
                log(f"Restart error: {e}", level="ERROR")
