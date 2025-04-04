import pandas as pd
import json
import os
import time
from config import (
    DRY_RUN,
    VERBOSE,
    is_aggressive,
    exchange,
    EXPORT_PATH,
    LOG_FILE_PATH,
    TELEGRAM_CHAT_ID,
    FIXED_PAIRS,
    trade_stats,
    TIMEZONE,
)
from stats import generate_summary, send_daily_report
from utils import (
    send_telegram_message,
    get_recent_logs,
    now,
    get_last_signal_time,
    load_state,
    save_state,
    log,
)
from telegram.telegram_utils import escape_markdown_v2
from ip_monitor import (
    enable_router_reboot_mode,
    cancel_router_reboot_mode,
    get_ip_status_message,
    force_ip_check_now,
)


def handle_telegram_command(message, state):
    """Handle Telegram commands sent to the bot."""
    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id", 0)

    log(f"Received command: {text} from chat ID {chat_id}", level="INFO")

    if "last_command" not in state:
        state["last_command"] = None

    elif text == "/help":
        message = (
            "🤖 *Available Commands:*\n\n"
            "📖 /help - Show this message\n"
            "📊 /summary - Show performance summary\n"
            "📜 /log - Export today's log to Telegram\n"
            "⚙️ /mode - Show current mode (SAFE/AGGRESSIVE)\n"
            "⏸️ /pause - Pause new trades\n"
            "▶️ /resume - Resume trading\n"
            "🛑 /stop - Stop after all positions close\n"
            "🚪 /shutdown - Exit bot after positions close\n"
            "📈 /open - Show open positions\n"
            "📉 /last - Show last closed trade\n"
            "💰 /balance - Show current USDC balance\n"
            "🚨 /panic - Force close all trades (confirmation)\n"
            "🔍 /status - Show bot status\n"
            "🧾 /debuglog - Show last 50 logs\n"
            "🔗 /pairstoday - Show active symbols today\n"
            "🔄 /router_reboot - Plan router reboot (30 min IP monitor)\n"
            "❌ /cancel_reboot - Cancel router reboot mode\n"
            "⛔ /cancel_stop - Cancel stop process if pending\n"
            "🌐 /ipstatus - Show current/previous IP + router mode\n"
            "📡 /forceipcheck - Force immediate IP check\n"
        )
        send_telegram_message(escape_markdown_v2(message), force=True)

    elif text == "/summary":
        summary = generate_summary()
        send_telegram_message(escape_markdown_v2(summary), force=True)

    elif text == "/pause":
        state["pause"] = True
        save_state(state)
        send_telegram_message(escape_markdown_v2("Trading paused."), force=True)
        log("Trading paused via /pause command.", level="INFO")

    elif text == "/resume":
        state["pause"] = False
        save_state(state)
        send_telegram_message(escape_markdown_v2("Trading resumed."), force=True)
        log("Trading resumed via /resume command.", level="INFO")

    elif text == "/stop":
        state = load_state()
        if state.get("stopping"):
            send_telegram_message("⚠️ Bot is already stopping...", force=True)
            log("Stop command ignored: bot is already stopping.", level="WARNING")
            return

        state["stopping"] = True
        save_state(state)

        open_trades = state.get("open_trades", [])
        if open_trades:
            max_timeout = max(t.get("timeout_timestamp", 0) for t in open_trades)
            now_ts = time.time()
            minutes_left = max(0, int((max_timeout - now_ts) / 60))
            if minutes_left < 0:
                minutes_left = 0

            msg = (
                f"🛑 Stop command received.\n"
                f"Waiting for {len(open_trades)} open trades to close.\n"
                f"Estimated time remaining: {minutes_left} min"
            )
        else:
            msg = "🛑 Stop command received.\nNo open trades. Bot will stop shortly."

        send_telegram_message(escape_markdown_v2(msg), force=True)
        log("Stop command received.", level="INFO")

    elif text == "/shutdown":
        state["shutdown"] = True
        save_state(state)
        send_telegram_message(
            escape_markdown_v2("Shutdown initiated. Waiting for positions to close..."),
            force=True,
        )
        log("Shutdown command received.", level="INFO")

    elif text == "/cancel_stop":
        state = load_state()
        state["stopping"] = False
        save_state(state)
        send_telegram_message(
            escape_markdown_v2(
                "✅ Stop process cancelled.\nBot will continue running."
            ),
            force=True,
        )
        log("Stop process cancelled via /cancel_stop command.", level="INFO")

    elif text == "/mode":
        mode = "AGGRESSIVE" if is_aggressive else "SAFE"
        send_telegram_message(escape_markdown_v2(f"Current mode: {mode}"), force=True)
        log(f"Mode command: Current mode is {mode}.", level="INFO")

    elif text == "/open":
        try:
            positions = exchange.fetch_positions()
            open_positions = [
                f"{p['symbol']} - {p['side'].upper()} {p['contracts']} @ {p['entryPrice']}"
                for p in positions
                if float(p.get("contracts", 0)) > 0
            ]
            msg = (
                "Open Positions:\n" + "\n".join(open_positions)
                if open_positions
                else "No open positions."
            )
            send_telegram_message(escape_markdown_v2(msg), force=True)
            log("Fetched open positions via /open command.", level="INFO")
        except Exception as e:
            error_msg = f"Failed to fetch open positions: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")

    elif text == "/last":
        try:
            df = pd.read_csv(EXPORT_PATH)
            if df.empty:
                send_telegram_message(
                    escape_markdown_v2("No trades logged yet."), force=True
                )
                log("No trades logged yet for /last command.", level="INFO")
            else:
                last = df.iloc[-1]
                msg = (
                    f"Last Trade:\n"
                    f"{last['Symbol']} - {last['Side']}\n"
                    f"Entry: {last['Entry Price']}, Exit: {last['Exit Price']}\n"
                    f"PnL: {last['PnL (%)']}% ({last['Result']})\n"
                    f"Held: {last['Held (min)']} min"
                )
                send_telegram_message(escape_markdown_v2(msg), force=True)
                log("Fetched last trade via /last command.", level="INFO")
        except Exception as e:
            error_msg = f"Failed to read last trade: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")

    elif text == "/balance":
        try:
            balance = exchange.fetch_balance()["total"]["USDC"]
            send_telegram_message(
                escape_markdown_v2(f"Balance: {round(balance, 2)} USDC"), force=True
            )
            log(
                f"Fetched balance: {round(balance, 2)} USDC via /balance command.",
                level="INFO",
            )
        except Exception as e:
            error_msg = f"Failed to fetch balance: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")

    elif text == "/panic":
        state["last_command"] = "/panic"
        send_telegram_message(
            escape_markdown_v2("Confirm PANIC close by replying YES"), force=True
        )
        log("Panic command received, awaiting confirmation.", level="INFO")

    elif text.upper() == "YES" and state.get("last_command") == "/panic":
        try:
            positions = exchange.fetch_positions()
            closed = []
            for p in positions:
                qty = float(p.get("contracts", 0))
                if qty > 0:
                    side = "sell" if p["side"] == "long" else "buy"
                    exchange.create_market_order(p["symbol"], side, qty)
                    closed.append(f"{p['symbol']} ({p['side']}, {qty})")
            if closed:
                msg = "Panic Close Executed:\n" + "\n".join(closed)
                send_telegram_message(escape_markdown_v2(msg), force=True)
                log("Panic close executed successfully.", level="INFO")
            else:
                send_telegram_message(
                    escape_markdown_v2("No open positions to close."), force=True
                )
                log("No open positions to close during panic.", level="INFO")
        except Exception as e:
            error_msg = f"Panic failed: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")
        finally:
            state["last_command"] = None
            save_state(state)

    elif text == "/status":
        try:
            current_time = now()
            last_sig = get_last_signal_time()
            idle = (
                f"{(current_time - last_sig).seconds // 60} min ago"
                if last_sig
                else "N/A"
            )

            balance = exchange.fetch_balance()["total"]["USDC"]
            mode = "AGGRESSIVE" if is_aggressive else "SAFE"
            paused = "Paused" if state.get("pause") else "Running"
            stopping = "Stopping after trades" if state.get("stopping") else ""

            open_syms = [
                p["symbol"]
                for p in exchange.fetch_positions()
                if float(p.get("contracts", 0)) > 0
            ]

            msg = (
                f"Bot Status\n"
                f"- Balance: {round(balance, 2)} USDC\n"
                f"- Mode: {mode}\n"
                f"- API Errors: {trade_stats.get('api_errors', 0)}\n"
                f"- Last Signal: {idle}\n"
                f"- Status: {paused} {stopping}\n"
                f"- Open: {', '.join(open_syms) if open_syms else 'None'}"
            )
            send_telegram_message(escape_markdown_v2(msg), force=True)
            log("Fetched bot status via /status command.", level="INFO")
        except Exception as e:
            error_msg = f"Status error: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")

    elif text == "/log":
        send_daily_report()
        log("Sent daily report via /log command.", level="INFO")

    elif text == "/router_reboot":
        enable_router_reboot_mode()
        log("Router reboot mode enabled via /router_reboot command.", level="INFO")

    elif text == "/cancel_reboot":
        cancel_router_reboot_mode()
        log("Router reboot mode cancelled via /cancel_reboot command.", level="INFO")

    elif text == "/debuglog":
        if DRY_RUN:  # Simplified check since VERBOSE == DRY_RUN
            logs = get_recent_logs()
            msg = f"Debug Log (last {len(logs.splitlines())} lines):\n\n{logs[:4000]}"
            send_telegram_message(escape_markdown_v2(msg), force=True)
            log("Sent debug log via /debuglog command.", level="INFO")
        else:
            send_telegram_message(
                escape_markdown_v2("Debug log only available in DRY_RUN mode."),
                force=True,
            )
            log("Debug log request denied: not in DRY_RUN mode.", level="INFO")

    elif text == "/ipstatus":
        msg = get_ip_status_message()
        send_telegram_message(escape_markdown_v2(msg), force=True)
        log("Fetched IP status via /ipstatus command.", level="INFO")

    elif text == "/forceipcheck":
        force_ip_check_now(handle_stop)
        log("Forced IP check via /forceipcheck command.", level="INFO")

    elif text == "/pairstoday":
        try:
            with open("data/dynamic_symbols.json", "r") as f:
                pairs = json.load(f)
            fixed = [p for p in pairs if p in FIXED_PAIRS]
            dynamic = [p for p in pairs if p not in FIXED_PAIRS]

            msg = (
                f"Active Pairs Today: {len(pairs)}\n\n"
                f"Fixed: {', '.join([p.split('/')[0] for p in fixed])}\n"
                f"Dynamic: {', '.join([p.split('/')[0] for p in dynamic])}"
            )
            send_telegram_message(escape_markdown_v2(msg), force=True)
            log("Fetched active pairs via /pairstoday command.", level="INFO")
        except Exception as e:
            error_msg = f"Failed to load symbol list: {str(e)}"
            send_telegram_message(escape_markdown_v2(error_msg), force=True)
            log(error_msg, level="ERROR")


def handle_stop():
    """
    Handle stopping the bot by setting the 'stopping' flag in the state.
    This is called by the IP monitor when an IP change is detected.
    """
    state = load_state()
    if state.get("stopping"):
        send_telegram_message("⚠️ Bot is already stopping...", force=True)
        log("Stop request ignored: bot is already stopping.", level="WARNING")
        return

    state["stopping"] = True
    save_state(state)

    open_trades = state.get("open_trades", [])
    if open_trades:
        max_timeout = max(t.get("timeout_timestamp", 0) for t in open_trades)
        now_ts = time.time()
        minutes_left = max(0, int((max_timeout - now_ts) / 60))
        if minutes_left < 0:
            minutes_left = 0

        msg = (
            f"🛑 Stop initiated due to IP change.\n"
            f"Waiting for {len(open_trades)} open trades to close.\n"
            f"Estimated time remaining: {minutes_left} min"
        )
    else:
        msg = "🛑 Stop initiated due to IP change.\nNo open trades. Bot will stop shortly."

    send_telegram_message(escape_markdown_v2(msg), force=True)
    log("Stop initiated due to IP change.", level="INFO")
