# telegram_commands.py
"""
Telegram command handlers for BinanceBot
Processes user commands and provides bot control with balance-aware enhancements
"""

import json
import os
import threading
import time
from threading import Lock, Thread

import pandas as pd

from common.config_loader import (
    DRY_RUN,
    EXPORT_PATH,
    FILTER_THRESHOLDS,
    LEVERAGE_MAP,
    RISK_PERCENT,
    SL_PERCENT,
    TP1_PERCENT,
    TP2_PERCENT,
    get_adaptive_risk_percent,
    get_adaptive_score_threshold,
    get_deposit_tier,
    get_max_positions,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.fail_stats_tracker import reset_failure_count
from core.trade_engine import close_real_trade, trade_manager
from missed_tracker import flush_best_missed_opportunities
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from symbol_activity_tracker import get_most_active_symbols
from telegram.registry import COMMAND_REGISTRY

# Add this import at the top of telegram_commands.py
from telegram.telegram_handler import handle_errors  # or wherever it's defined
from telegram.telegram_ip_commands import handle_ip_and_misc_commands
from telegram.telegram_utils import escape_markdown_v2, register_command, send_telegram_message
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


def _initiate_stop(reason, stop_event=None):
    """
    Initiate stop process with enhanced position handling
    """
    if stop_event:
        stop_event.set()
        log(f"[Stop] Setting global stop_event for {reason}", level="INFO")
    state = load_state()
    if state.get("stopping"):
        send_telegram_message("⚠️ Bot is already stopping…", force=True)
        return False
    state["stopping"] = True
    save_state(state)
    try:
        if DRY_RUN:
            open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            positions = exchange.fetch_positions()
            open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]
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


# --- Converted Commands in New Format -----------------------------------


@register_command("/regenpriority")
@handle_errors
def cmd_regenpriority(message, state=None, stop_event=None):
    """
    Regenerate priority pairs based on current market conditions.
    Usage: /regenpriority
    """
    try:
        from core.priority_evaluator import regenerate_priority_pairs

        result = regenerate_priority_pairs()
        send_telegram_message(result, force=True, parse_mode="MarkdownV2")
        log("[Telegram] Priority pairs regenerated via command", level="INFO")
        return True
    except Exception as e:
        log(f"[Telegram] Error regenerating priority pairs: {e}", level="ERROR")
        send_telegram_message(f"❌ Error: {e}", force=True)
        return False


@register_command("/prioritypairs")
@handle_errors
def cmd_prioritypairs(message, state=None, stop_event=None):
    """
    Show current priority pairs and their scores.
    Usage: /prioritypairs
    """
    try:
        from core.priority_evaluator import gather_symbol_data, get_priority_score, load_priority_pairs

        # Load current priority pairs
        priority_pairs = load_priority_pairs()

        # Get fresh data to show current scores
        symbols_data = gather_symbol_data() if "gather_symbol_data" in dir() else {}

        # Calculate scores for display
        pairs_with_scores = []
        for symbol in priority_pairs:
            if symbol in symbols_data:
                score = get_priority_score(symbol, symbols_data[symbol])
                price = symbols_data[symbol].get("price", 0)
                pairs_with_scores.append((symbol, score, price))
            else:
                pairs_with_scores.append((symbol, "N/A", "N/A"))

        # Sort by score
        pairs_with_scores.sort(key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)

        # Format message
        if pairs_with_scores:
            message = "📊 *Current Priority Pairs*\n\n"
            for i, (symbol, score, price) in enumerate(pairs_with_scores):
                if score == "N/A":
                    message += f"{i+1}. `{symbol}`: Score N/A\n"
                else:
                    message += f"{i+1}. `{symbol}`: Score {score:.3f} | ${price:.4f}\n"

            # Add update time
            import json
            import os
            from datetime import datetime

            PRIORITY_JSON_PATH = "data/priority_pairs.json"
            if os.path.exists(PRIORITY_JSON_PATH):
                with open(PRIORITY_JSON_PATH, "r") as f:
                    data = json.load(f)
                update_time = data.get("updated_at", "Unknown")
                if update_time != "Unknown":
                    try:
                        dt = datetime.fromisoformat(update_time)
                        update_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pass
                message += f"\nLast updated: {update_time}"
        else:
            message = "❌ No priority pairs found"

        send_telegram_message(message, force=True, parse_mode="MarkdownV2")
        return True
    except Exception as e:
        log(f"[TelegramCommand] Error in prioritypairs: {e}", level="ERROR")
        send_telegram_message(f"❌ Error retrieving priority pairs: {str(e)}", force=True)
        return False


@register_command("status")
@handle_errors
def cmd_status(message, state, stop_event=None):
    """
    Show current bot status including mode, balance, risk, and open positions.
    """
    from core.trade_engine import open_positions_count
    from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
    from utils_core import (
        get_adaptive_risk_percent,
        get_cached_balance,
        get_deposit_tier,
        get_max_positions,
        get_min_net_profit,
        get_runtime_config,
    )

    balance = get_cached_balance()
    tier = get_deposit_tier()
    runtime_config = get_runtime_config()

    # Limit displayed risk per tier
    requested_risk = runtime_config.get("risk_percent", get_adaptive_risk_percent(tier))
    max_allowed_risk = get_adaptive_risk_percent(tier)
    current_risk = min(requested_risk, max_allowed_risk)

    max_pos = get_max_positions(balance)
    min_profit = get_min_net_profit(balance)

    msg = (
        f"🔍 *Bot Status*\n"
        f"Mode: `{'DRY_RUN' if DRY_RUN else 'REAL_RUN'}`\n"
        f"Stopping: `{state.get('stopping', False)}`\n"
        f"Balance: `{balance:.2f}` USDC\n"
        f"Risk Tier: `{tier}`\n"
        f"Max Positions: `{max_pos}`\n\n"
        f"*Risk Metrics:*\n"
        f"Total Exposure: `{state.get('exposure', 0.0):.1f}%`\n"
        f"Max Single Risk: `{state.get('max_risk', 0.0):.1f}%`\n"
        f"Active Positions: `{open_positions_count}`\n"
        f"Risk Per Trade: `{current_risk * 100:.1f}%`\n"
        f"TP1/TP2/SL: `{TP1_PERCENT * 100:.1f}%/{TP2_PERCENT * 100:.1f}%/{TP1_PERCENT * 100:.1f}%`\n"
        f"Min Profit Target: `{min_profit:.2f}` USDC\n\n"
        f"Open Positions: `{open_positions_count}`"
    )

    send_telegram_message(escape_markdown_v2(msg))


@register_command("/help")
@handle_errors
def cmd_help(message, state=None, stop_event=None):
    """
    Display available commands and their descriptions.
    Usage: /help [command_name]
    """
    try:
        command_parts = message.get("text", "").strip().split()

        # If specific command help requested
        if len(command_parts) > 1:
            specific_cmd = f"/{command_parts[1].lower().lstrip('/')}"
            cmd_entry = COMMAND_REGISTRY.get(specific_cmd)

            if cmd_entry:
                help_text = cmd_entry["help"] or "No description available."
                send_telegram_message(f"Help for {specific_cmd}:\n\n{help_text}", force=True)
                return True
            else:
                send_telegram_message(f"Command {specific_cmd} not found. Try /help for a list of commands.", force=True)
                return False

        # General help - list all registered commands first
        help_msg = "🤖 *Available Commands:*\n\n"

        # Add registered commands
        for cmd, entry in sorted(COMMAND_REGISTRY.items()):
            doc = entry["help"] or ""
            # Extract first line of docstring as short description
            short_desc = doc.split("\n")[0].strip() if doc else "No description"
            help_msg += f"{cmd} - {short_desc}\n"

        # Legacy commands - this section will be removed as commands are migrated
        legacy_commands = """
📡 /forceipcheck - Force immediate IP check
📉 /last - Show last closed trade
📜 /log - Export today's log to Telegram
⚖️ /mode - Show strategy bias and score
📈 /open - Show open positions
🔄 /restart - Restart bot after closing positions
⚠️ /risk - Adjust risk level (balance-aware)
🔄 /router_reboot - Plan router reboot
🚪 /shutdown - Exit bot after positions close
🛑 /stop - Stop after all positions close
🚨 /panic - Force close all trades (confirmation)
📊 /summary - Show performance summary
⚙️ /filters - Adjust pair filters (with dynamic values)
🔧 /runtime - Show current runtime config
🚫 /signalblocks - Show currently blocked symbols
🔓 /unblock - Manually unblock a symbol
📉 /failstats - Show failure statistics for all symbols
❌ /reasons - Show signal rejection reasons
📈 /pairstoday - Show today's selected pairs
🧠 /signalconfig - Show adaptive signal config
🧩 /statuslog - Show 10-minute activity report
"""

        send_telegram_message(help_msg + legacy_commands, force=True, parse_mode="MarkdownV2")
        log("[Telegram] Help information sent", level="INFO")
        return True
    except Exception as e:
        log(f"[Telegram] Error in help command: {e}", level="ERROR")
        send_telegram_message(f"❌ Error displaying help: {e}", force=True)
        return False


@register_command("/stop")
@handle_errors
def cmd_stop(message, state=None, stop_event=None):
    """
    Stop the bot after closing all positions.
    Usage: /stop
    """
    try:
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
        return True
    except Exception as e:
        log(f"[Telegram] Error in stop command: {e}", level="ERROR")
        send_telegram_message(f"❌ Error stopping bot: {e}", force=True)
        return False


@register_command("/signalconfig")
@handle_errors
def cmd_signalconfig(message, state=None, stop_event=None):
    """
    Show current adaptive signal configuration with key trading parameters and relax factors.
    Usage: /signalconfig
    """
    try:
        config = get_runtime_config()

        # Add current trading parameters
        balance = get_cached_balance()
        tier = get_deposit_tier()

        # Get effective values if not in runtime config
        effective_tp1 = config.get("tp1_percent", TP1_PERCENT)
        effective_tp2 = config.get("tp2_percent", TP2_PERCENT)
        effective_sl = config.get("sl_percent", SL_PERCENT)
        effective_risk = config.get("risk_percent", get_adaptive_risk_percent(tier))

        msg = (
            "*Current Adaptive Signal Config:*\n"
            f"Balance: ${balance:.2f} (Tier: {tier})\n"
            f"Risk Percent: {effective_risk*100:.1f}%\n"
            f"TP1 Percent: {effective_tp1*100:.1f}%\n"
            f"TP2 Percent: {effective_tp2*100:.1f}%\n"
            f"SL Percent: {effective_sl*100:.1f}%\n"
            f"Max Positions: {get_max_positions()}\n"
            f"Min Score: {get_adaptive_score_threshold(tier):.1f}\n"
            "\n*Runtime Config:*\n"
        )

        # Add all runtime config items
        for k, v in config.items():
            msg += f"`{k}` = `{v}`\n"

        # Add per-symbol relax factors
        import os

        from common.config_loader import SYMBOLS_FILE
        from utils_core import load_json_file

        if os.path.exists(SYMBOLS_FILE):
            with open(SYMBOLS_FILE, "r") as f:
                active_symbols = json.load(f)
        else:
            active_symbols = []

        filter_data = load_json_file("data/filter_adaptation.json")
        if filter_data:
            msg += "\n*Per-Symbol Relax Factors:*\n"
            for symbol in active_symbols:
                norm = symbol.replace("/", "").upper()
                rf = filter_data.get(norm, {}).get("relax_factor", config.get("relax_factor", "N/A"))
                msg += f"`{symbol}`: `{rf}`\n"

        send_telegram_message(msg, parse_mode="MarkdownV2")
        log("[Telegram] Signal config information sent", level="INFO")
        return True
    except Exception as e:
        log(f"[Telegram] Error in signalconfig command: {e}", level="ERROR")
        send_telegram_message(f"❌ Error fetching signal config: {e}", force=True)
        return False


@register_command("/mtfstatus")
@handle_errors
def cmd_mtfstatus(message, state=None, stop_event=None):
    """
    Show current Multi-Timeframe strategy configuration.
    Usage: /mtfstatus
    """
    try:
        config = get_runtime_config()
        multitf_enabled = config.get("USE_MULTITF_LOGIC", False)
        rsi_threshold = config.get("rsi_threshold", "N/A")

        message = "\U0001f9e0 *Multi-Timeframe Status*\n" f"\n✅ Enabled: `{multitf_enabled}`" f"\n📊 Timeframes: `3m`, `5m`, `15m`" f"\n📈 RSI Threshold: `{rsi_threshold}`"

        send_telegram_message(message, parse_mode="MarkdownV2")
        log("[Telegram] MTF status information sent", level="INFO")
        return True
    except Exception as e:
        log(f"[Telegram] Error in mtfstatus command: {e}", level="ERROR")
        send_telegram_message(f"❌ Error in /mtfstatus: {e}", force=True)
        return False


@register_command("/signalstats")
@handle_errors
def cmd_signalstats(_message, _state=None, _stop_event=None):
    """
    Display statistics about signal components and their effectiveness.
    Usage: /signalstats
    """
    try:
        with open("data/component_tracker_log.json", "r") as f:
            data = json.load(f)

        components = data.get("components", {})
        if not components:
            send_telegram_message("No signal statistics available yet.")
            return True

        # Calculate total trades from most frequent component
        most_frequent = max(components.values(), key=lambda x: x["count"]) if components else {"count": 0}
        total_trades = most_frequent["count"]

        response = "📊 Signal Component Statistics:\n\n"

        # Sort by frequency
        sorted_components = sorted(components.items(), key=lambda x: x[1]["count"], reverse=True)

        for component, stats in sorted_components:
            count = stats["count"]
            successful = stats.get("successful", 0)
            winrate = successful / count if count > 0 else 0
            last_used = stats.get("last_used", "").split("T")[0] if "last_used" in stats else "N/A"

            percentage = (count / total_trades) * 100 if total_trades > 0 else 0
            response += f"• {component}: Used in {percentage:.1f}% of trades ({count} times)\n"
            response += f"  Win rate: {winrate:.1%}, Last used: {last_used}\n\n"

        # Add candlestick rejection info if available
        rejections = data.get("candlestick_rejections", 0)
        if rejections > 0:
            response += f"🕯️ Candlestick patterns rejected {rejections} potential trades\n"

        send_telegram_message(response)
        return True

    except Exception as e:
        log(f"Error in signalstats command: {e}", level="ERROR")
        send_telegram_message(f"Error retrieving signal statistics: {e}")
        return False


@register_command("/missedlog")
@handle_errors
def cmd_missedlog(message, _state=None, _stop_event=None):
    """
    Display recent missed signals and reasons.
    Usage: /missedlog [number_of_entries]
    """
    from core.missed_signal_logger import get_recent_missed_signals

    try:
        limit = 5  # Default limit

        # Check if number of entries was specified in the command
        command_parts = message.get("text", "").strip().split()
        if len(command_parts) > 1 and command_parts[1].isdigit():
            limit = min(int(command_parts[1]), 10)  # Allow up to 10

        missed_signals = get_recent_missed_signals(limit)

        if not missed_signals:
            send_telegram_message("No missed signals logged yet.")
            return True

        response = f"📉 Last {len(missed_signals)} Missed Signals:\n\n"

        for idx, signal in enumerate(missed_signals, 1):
            symbol = signal.get("symbol", "Unknown")
            score = signal.get("score", 0)
            reason = signal.get("reason", "Unknown")
            breakdown = signal.get("breakdown", {})
            timestamp = signal.get("timestamp", "").split("T")[0]

            # Format reason nicely
            if reason == "signal_combo_fail":
                reason_text = "No valid signal combination (1+1 rule)"
            elif reason == "insufficient_score":
                reason_text = f"Score {score} below threshold"
            else:
                reason_text = reason.replace("_", " ").capitalize()

            # Find active components
            active_components = [comp for comp, val in breakdown.items() if val > 0]
            components_str = ", ".join(active_components) if active_components else "None"

            response += f"{idx}. {symbol} ({timestamp}):\n"
            response += f"   Score: {score}, Active: {components_str}\n"
            response += f"   Rejected: {reason_text}\n\n"

        send_telegram_message(response)
        return True

    except Exception as e:
        log(f"Error in missedlog command: {e}", level="ERROR")
        send_telegram_message(f"Error retrieving missed signals log: {e}")
        return False


# --- Legacy Command Handlers (to be migrated) --------------------------

# These functions will be maintained until they're migrated to the new format
# This ensures backward compatibility during the transition


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


@register_command("/signalblocks")
@handle_errors
def cmd_signalblocks(_message=None, _state=None, _stop_event=None):
    from core.fail_stats_tracker import get_symbol_risk_factor
    from utils_core import get_runtime_config

    runtime_config = get_runtime_config()
    blocked_symbols = runtime_config.get("blocked_symbols", {})

    if not blocked_symbols:
        send_telegram_message("No symbols have risk adjustments. ✅")
        return True

    msg = "🔄 Symbol Risk Factors:\n\n"

    for symbol, block_info in blocked_symbols.items():
        risk_factor, _ = get_symbol_risk_factor(symbol)
        failures = block_info.get("total_failures", 0)

        risk_category = "Low" if risk_factor >= 0.7 else "Medium" if risk_factor >= 0.4 else "High"

        msg += f"• {symbol}\n" f"  Risk Level: {risk_category} ({risk_factor:.2f}x)\n" f"  Failures: {failures}\n\n"

    send_telegram_message(msg, force=True)
    return True


@handle_errors
def cmd_unblock(update, context):
    """Manually unblock a symbol: /unblock BTCUSDC"""
    try:
        if not context.args:
            update.message.reply_text("Usage: /unblock SYMBOL (e.g., /unblock BTCUSDC)")
            return

        # Handle both formats: BTCUSDC and BTC/USDC
        input_symbol = context.args[0].upper()

        # Convert to standard format (with slash) if needed
        if "/" not in input_symbol and "USDC" in input_symbol:
            # Convert BTCUSDC to BTC/USDC
            symbol = input_symbol.replace("USDC", "/USDC")
        else:
            symbol = input_symbol

        from utils_core import get_runtime_config, update_runtime_config

        runtime_config = get_runtime_config()
        blocked_symbols = runtime_config.get("blocked_symbols", {})

        if symbol not in blocked_symbols:
            update.message.reply_text(f"{symbol} is not blocked.")
            return

        # Remove block
        del blocked_symbols[symbol]
        runtime_config["blocked_symbols"] = blocked_symbols
        update_runtime_config(runtime_config)

        # Reset failure count
        reset_failure_count(symbol)

        update.message.reply_text(f"✅ {symbol} has been unblocked and failure count reset.")
    except Exception as e:
        update.message.reply_text(f"Error unblocking symbol: {e}")


@handle_errors
def cmd_failstats(_message=None, _state=None, _stop_event=None):
    """Show failure statistics for all symbols."""
    try:
        from core.fail_stats_tracker import get_signal_failure_stats

        failure_stats = get_signal_failure_stats()

        if not failure_stats:
            send_telegram_message("No failure statistics available. ✅")
            return

        msg = "📊 Signal Failure Statistics:\n\n"

        # Sort by total failures descending
        sorted_symbols = sorted(failure_stats.items(), key=lambda x: sum(x[1].values()), reverse=True)

        for symbol, reasons in sorted_symbols[:10]:  # Show top 10
            total_failures = sum(reasons.values())

            msg += f"• {symbol}: {total_failures} failures\n"

            # Show breakdown of reasons
            sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)
            for reason, count in sorted_reasons[:3]:  # Top 3 reasons
                msg += f"  - {reason}: {count}\n"
            msg += "\n"

        if len(sorted_symbols) > 10:
            msg += f"... and {len(sorted_symbols) - 10} more symbols"

        send_telegram_message(msg)
        return True
    except Exception as e:
        send_telegram_message(f"Error fetching failure stats: {e}")
        return False


def handle_risk_command(message):
    """
    Adjust risk level with balance-aware limits
    """
    try:
        parts = message.get("text", "").strip().split()
        balance = get_cached_balance()
        tier = get_deposit_tier()
        max_recommended_risk = get_adaptive_risk_percent(balance)

        if len(parts) == 1:
            current_risk = RISK_PERCENT if RISK_PERCENT else get_adaptive_risk_percent(balance)
            msg = (
                f"Current Risk Level: {current_risk*100:.1f}%\n"
                f"Your Balance: ${balance:.2f} (Tier: {tier})\n"
                f"Recommended Max Risk: {max_recommended_risk*100:.1f}%\n"
                "Use /risk <value> to set new risk (e.g., /risk 0.02 for 2%)"
            )
            send_telegram_message(msg, force=True)
        else:
            new_risk = float(parts[1])

            # Balance-aware limits by tier
            if tier == "Small":
                max_allowed_risk = 0.02  # 2.0% max for micro/small accounts
            elif tier == "Medium":
                max_allowed_risk = 0.03  # 3.0% max for medium accounts
            else:
                max_allowed_risk = 0.05  # 5.0% max for standard accounts

            if new_risk < 0.005:  # 0.5% minimum
                send_telegram_message("❌ Risk must be at least 0.005 (0.5%)", force=True)
            elif new_risk > max_allowed_risk:
                send_telegram_message(f"❌ For your balance (${balance:.2f}), maximum risk is {max_allowed_risk*100:.1f}%\n" f"Recommended: {max_recommended_risk*100:.1f}%", force=True)
            else:
                from utils_core import update_runtime_config

                update_runtime_config({"risk_percent": new_risk})
                send_telegram_message(f"✅ Risk level set to {new_risk*100:.1f}%\n" f"(Recommended for ${balance:.2f}: {max_recommended_risk*100:.1f}%)", force=True)
                log(f"Risk level set to {new_risk*100:.1f}% via /risk command", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to set risk: {e}", force=True)
        log(f"Risk command error: {e}", level="ERROR")


def handle_filters_command(message):
    """
    Adjust pair filters with dynamic filter display
    """
    try:
        from common.config_loader import set_filter_thresholds

        parts = message.get("text", "").strip().split()

        # Get current runtime config
        runtime_config = get_runtime_config()
        relax_factor = runtime_config.get("relax_factor", 1.0)

        if len(parts) == 1:
            try:
                with open("data/filter_settings.json", "r") as f:
                    filters = json.load(f)

                # Get current symbol if we have an active one
                current_filters = {}
                if trade_manager._trades:
                    sample_symbol = list(trade_manager._trades.keys())[0]
                    if sample_symbol in FILTER_THRESHOLDS:
                        current_filters = FILTER_THRESHOLDS[sample_symbol]
                    else:
                        current_filters = FILTER_THRESHOLDS.get("default", {})
                else:
                    current_filters = FILTER_THRESHOLDS.get("default", {})

                msg = (
                    f"Current Filters:\n"
                    f"ATR: {filters['atr_percent']*100:.2f}%\n"
                    f"Volume: {filters['volume_usdc']:,.0f} USDC\n"
                    f"Relax Factor: {relax_factor:.2f}\n"
                    f"Current Thresholds:\n"
                    f"  ATR: {current_filters.get('atr', 0):.4f}\n"
                    f"  ADX: {current_filters.get('adx', 0):.1f}\n"
                    f"  BB: {current_filters.get('bb', 0):.4f}\n"
                    "Use /filters <atr_percent> <volume_usdc> to set new filters"
                )
            except Exception:
                msg = f"No filters set. Relax Factor: {relax_factor:.2f}\n" "Use /filters <atr_percent> <volume_usdc> to set new filters"
            send_telegram_message(msg, force=True)
        else:
            atr_percent = float(parts[1])
            volume_usdc = float(parts[2])
            set_filter_thresholds(atr_percent, volume_usdc)
            send_telegram_message(f"✅ Filters updated: ATR={atr_percent*100:.2f}%, Volume={volume_usdc:,.0f} USDC\n" f"(Current Relax Factor: {relax_factor:.2f})", force=True)
            log(f"Filters updated via /filters command: ATR={atr_percent*100:.2f}%, Volume={volume_usdc:,.0f} USDC", level="INFO")
    except Exception as e:
        send_telegram_message(f"❌ Failed to set filters: {e}", force=True)
        log(f"Filters command error: {e}", level="ERROR")


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


def handle_panic(message, state, stop_event=None):
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


def handle_shutdown(message, state, stop_event=None):
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


# --- Main Command Handler (Updated) ------------------------------------


def handle_telegram_command(message, state, stop_event=None):
    """
    Main Telegram command handler using registry lookup with fallback to legacy handlers.
    """
    # At the beginning of the function
    log(f"All registered commands: {list(COMMAND_REGISTRY.keys())}", level="DEBUG")
    # Skip stale messages
    message_date = message.get("date", 0)
    session_start_time = state.get("session_start_time", 0)
    if message_date and session_start_time and message_date < session_start_time:
        log(f"Ignoring stale command from previous session: {message.get('text', '').strip()}", level="DEBUG")
        return

    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id", 0)
    log(f"Received command: {text} from chat ID {chat_id}", level="DEBUG")

    if "last_command" not in state:
        state["last_command"] = None

    with command_lock:  # Thread-safe command processing
        # First check for IP and misc commands (legacy handling for now)
        if text in [
            "/router_reboot",
            "/cancel_reboot",
            "/ipstatus",
            "/forceipcheck",
            "/pairstoday",
            "/debuglog",
            "/log",
            "/runtime",
            "/reasons",
        ] or text.startswith("/close_dry"):
            handle_ip_and_misc_commands(text, _initiate_stop)
            return

        # Check command registry for registered commands
        cmd_entry = COMMAND_REGISTRY.get(text)
        if cmd_entry:
            try:
                cmd_entry["handler"](message, state, stop_event)
                return
            except Exception as e:
                log(f"[Telegram] Error executing {text}: {e}", level="ERROR")
                send_telegram_message(f"❌ Error executing {text}: {e}", force=True)
                return

        # Check for commands with arguments
        command_parts = text.split()
        base_command = command_parts[0] if command_parts else ""

        for cmd_text, cmd_entry in COMMAND_REGISTRY.items():
            if base_command == cmd_text:
                try:
                    cmd_entry["handler"](message, state, stop_event)
                except Exception as e:
                    log(f"[Telegram] Error executing {base_command}: {e}", level="ERROR")
                    send_telegram_message(f"❌ Error executing {base_command}: {e}", force=True)
                return

        # Legacy command handling (to be migrated)
        if text == "/signalblocks":
            cmd_signalblocks({"message": message}, {})
        elif text.startswith("/unblock"):
            # Parse the command arguments
            parts = text.split()
            cmd_unblock({"message": message}, {"args": parts[1:] if len(parts) > 1 else []})
        elif text == "/failstats":
            cmd_failstats({"message": message}, {})
        elif text == "/goals":
            handle_goals_command()
        elif text.startswith("/risk"):
            handle_risk_command(message)
        elif text.startswith("/filters"):
            handle_filters_command(message)
        elif text == "/statuslog":
            from core.status_logger import log_symbol_activity_status_to_telegram

            try:
                log_symbol_activity_status_to_telegram()
            except Exception as e:
                send_telegram_message(f"[StatusLog Error] Could not generate status log: {e}")
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
                tier = get_deposit_tier()
                send_telegram_message(f"💰 Balance: {balance} USDC\n📊 Risk Tier: {tier}", force=True)
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
        elif text == "/runtime":
            handle_runtime_command()
            log("Handled /runtime command.", level="INFO")
        elif text == "/panic" or text == "yes":
            handle_panic(message, state, stop_event)
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
        elif text == "/summary":
            try:
                summary = generate_summary()
                # Add balance-aware context
                balance = get_cached_balance()
                tier = get_deposit_tier()
                runtime_config = get_runtime_config()
                current_risk = runtime_config.get("risk_percent", get_adaptive_risk_percent(tier))

                if DRY_RUN:
                    open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
                else:
                    positions = exchange.fetch_positions()
                    open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

                msg = (
                    summary + f"\n\n*Account Info*:\n"
                    f"Balance: {balance:.2f} USDC\n"
                    f"Risk Tier: {tier}\n"
                    f"Active Risk: {current_risk*100:.1f}%\n"
                    f"Max Positions: {get_max_positions()}\n"
                    "\n*Open Positions*:\n" + ("\n".join(open_details) if open_details else "None")
                )
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent enhanced summary via /summary.", level="INFO")
            except Exception as e:
                send_telegram_message(f"❌ Failed to generate summary: {e}", force=True)
                log(f"Summary error: {e}", level="ERROR")
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
        else:
            # Command not recognized
            send_telegram_message("Command not recognized. Try /help for a list of commands.", force=True)
