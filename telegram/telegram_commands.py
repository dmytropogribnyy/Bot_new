import os
import threading
import time
from threading import Lock, Thread

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH, LEVERAGE_MAP, trade_stats
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.trade_engine import close_real_trade, trade_manager
from main import stop_event
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from telegram.telegram_ip_commands import handle_ip_and_misc_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, get_last_signal_time, load_state, save_state
from utils_logging import log, now

command_lock = Lock()


# --- Helpers ------------------------------------------------------------
def _format_pos_real(p):
    """Format real position for Telegram display with enhanced error handling"""
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
    """Format dry-run position for Telegram display with enhanced error handling"""
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
    """Monitor stop process with timeout warning and improved cleanup"""
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
    """Initiate stop process with enhanced position handling"""
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


def handle_stop_command():
    """Enhanced stop command with active position closing and stop_event triggering"""
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
    """Emergency force closure of all positions and orders with timeout."""

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
    """Gracefully shutdown bot with proper position and order closure."""
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


def handle_telegram_command(message, state):
    """Main Telegram command handler with thread safety and enhanced reliability"""
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
        ] or text.startswith("/close_dry"):
            handle_ip_and_misc_commands(text, _initiate_stop)
            return
        elif text == "/help":
            help_msg = (
                "🤖 Available Commands:\n\n"
                "💰 /balance - Show current USDC balance\n"
                "❌ /cancel_reboot - Cancel router reboot mode\n"
                "⛔ /cancel_stop - Cancel stop process if pending\n"
                "🔒 /close_dry - Close a DRY position (e.g., /close_dry BTC/USDC)\n"
                "🧾 /debuglog - Show last 50 logs\n"
                "📡 /forceipcheck - Force immediate IP check\n"
                "📊 /heatmap - Generate 7-day score heatmap\n"
                "📖 /help - Show this message\n"
                "🌐 /ipstatus - Show current/previous IP + router mode\n"
                "📉 /last - Show last closed trade\n"
                "📜 /log - Export today's log to Telegram\n"
                "⚖️ /mode - Show strategy bias and score\n"
                "📈 /open - Show open positions\n"
                "🔄 /restart - Restart bot after closing positions\n"
                "🔄 /router_reboot - Plan router reboot\n"
                "▶️ /resume_after_ip - Resume after IP change\n"
                "🚪 /shutdown - Exit bot after positions close\n"
                "🛑 /stop - Stop after all positions close\n"
                "🚨 /panic - Force close all trades (confirmation)\n"
                "🔍 /status - Show bot status\n"
                "📊 /summary - Show performance summary"
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
            try:
                if DRY_RUN:
                    open_list = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
                    header = "Open DRY positions:"
                else:
                    positions = exchange.fetch_positions()
                    open_list = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]
                    header = "Open positions:"
                msg = header + "\n" + "\n".join(open_list) if open_list else f"{header} none."
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent /open positions.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to fetch open positions: {e}", force=True)
                log(f"Open positions error: {e}", level="ERROR")
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
        elif text == "/status":
            try:
                current = now()
                last_sig = get_last_signal_time()
                idle = f"{(current - last_sig).seconds//60} min ago" if last_sig else "N/A"
                balance = round(float(get_cached_balance()), 2)
                score = round(get_aggressiveness_score(), 2)
                mode = "🔥 HIGH" if score >= 3.5 else "⚡ MODERATE" if score >= 2.5 else "🧊 LOW"

                # Risk percent based on balance (for small deposit awareness)
                from common.config_loader import get_adaptive_risk_percent

                risk = get_adaptive_risk_percent(balance) * 100

                if state.get("shutdown"):
                    status = "🔌 Shutdown in progress"
                elif state.get("stopping"):
                    try:
                        positions = exchange.fetch_positions() if not DRY_RUN else []
                        open_syms = [p["symbol"] for p in positions if float(p.get("contracts", 0)) > 0]
                        status = f"🛑 Stopping after trades ({len(open_syms)} open)" if open_syms else "🛑 Stopping — no open trades"
                    except Exception as e:
                        status = "🛑 Stopping — error fetching trades"
                        log(f"[Status] Failed to fetch positions for status: {e}", level="ERROR")
                else:
                    status = "✅ Running"

                if DRY_RUN:
                    open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
                else:
                    try:
                        positions = exchange.fetch_positions()
                        open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]
                    except Exception as e:
                        log(f"[Status] Failed fetch: {e}", level="ERROR")
                        send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
                        open_details = []

                # Enhanced status with risk info
                msg = (
                    "<b>Bot Status</b>\n"
                    f"- Balance: {balance} USDC\n"
                    f"- Risk Level: {risk:.1f}%\n"
                    f"- Aggressiveness: {mode} ({score})\n"
                    f"- API Errors: {trade_stats.get('api_errors',0)}\n"
                    f"- Last Signal: {idle}\n"
                    f"- Status: {status}\n"
                    f"- Open Positions:\n" + ("\n".join(open_details) if open_details else "None")
                )
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent /status.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Status error: {e}", force=True)
                log(f"Status error: {e}", level="ERROR")
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
