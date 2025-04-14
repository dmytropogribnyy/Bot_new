# telegram_commands.py

import time
from threading import Lock

import pandas as pd

from config import (
    AGGRESSIVENESS_THRESHOLD,
    DRY_RUN,
    EXPORT_PATH,
    LOG_LEVEL,
    exchange,
    trade_stats,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.trade_engine import trade_manager
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from telegram.telegram_ip_commands import handle_ip_and_misc_commands
from telegram.telegram_utils import send_telegram_message
from utils_core import (
    get_cached_balance,
    get_cached_positions,
    get_last_signal_time,
    load_state,
    save_state,
)
from utils_logging import log, now

# Добавляем лок для синхронизации команд
command_lock = Lock()


def handle_telegram_command(message, state):
    """Handle Telegram commands sent to the bot."""
    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id", 0)

    log(f"Received command: {text} from chat ID {chat_id}", level="DEBUG")

    if "last_command" not in state:
        state["last_command"] = None

    with command_lock:
        if text in [
            "/router_reboot",
            "/cancel_reboot",
            "/ipstatus",
            "/forceipcheck",
            "/pairstoday",
            "/debuglog",
            "/log",
        ] or text.startswith("/close_dry"):
            handle_ip_and_misc_commands(text, handle_stop)
            return

        elif text == "/help":
            message = (
                "🤖 Available Commands:\n\n"
                "💰 /balance - Show current USDC balance\n"
                "❌ /cancel_reboot - Cancel router reboot mode\n"
                "⛔ /cancel_stop - Cancel stop process if pending\n"
                "🔒 /close_dry - Close a DRY position (DRY_RUN only, e.g., /close_dry BTC/USDC)\n"
                "🧾 /debuglog - Show last 50 logs\n"
                "📡 /forceipcheck - Force immediate IP check\n"
                "📊 /heatmap - Generate score heatmap for the last 7 days\n"
                "📖 /help - Show this message\n"
                "🌐 /ipstatus - Show current/previous IP + router mode\n"
                "📉 /last - Show last closed trade\n"
                "📜 /log - Export today's log to Telegram\n"
                "⚖️ /mode - Show dynamic strategy bias (based on winrate, volatility)\n"
                "📈 /open - Show open positions\n"
                "🔗 /pairstoday - Show active symbols today\n"
                "🚨 /panic - Force close all trades (confirmation)\n"
                "▶️ /resume_after_ip - Resume bot after IP change (REAL_RUN only)\n"
                "🔄 /router_reboot - Plan router reboot (30 min IP monitor)\n"
                "🚪 /shutdown - Exit bot after positions close\n"
                "🔍 /status - Show bot status\n"
                "🛑 /stop - Stop after all positions close\n"
                "📊 /summary - Show performance summary"
            ).strip()
            send_telegram_message(message, force=True, parse_mode="")
            if LOG_LEVEL == "DEBUG":
                log("Sent help message.", level="DEBUG")

        elif text == "/summary":
            summary = generate_summary()
            send_telegram_message(summary, force=True, parse_mode="MarkdownV2")
            if LOG_LEVEL == "DEBUG":
                log("Sent summary via /summary command.", level="DEBUG")

        elif text == "/heatmap":
            generate_score_heatmap(days=7)
            if LOG_LEVEL == "DEBUG":
                log("Generated score heatmap via /heatmap command.", level="DEBUG")

        elif text == "/stop":
            state = load_state()
            log(f"State before /stop: {state}", level="DEBUG")

            if state.get("stopping"):
                send_telegram_message("⚠️ Bot is already stopping...", force=True, parse_mode="")
                log("Stop command ignored: bot is already stopping.", level="WARNING")
                return

            state["stopping"] = True
            save_state(state)

            state = load_state()
            log(f"State after /stop: {state}", level="DEBUG")

            if not state.get("stopping"):
                log("Failed to set stopping flag — retrying...", level="ERROR")
                state["stopping"] = True
                save_state(state)

            open_trades = state.get("open_trades", [])
            if open_trades:
                now_ts = time.time()
                max_timeout = max(t.get("timeout_timestamp", 0) for t in open_trades)
                minutes_left = max(0, int((max_timeout - now_ts) / 60))

                msg = (
                    f"🛑 Stop command received.\n"
                    f"Waiting for {len(open_trades)} open trades to close.\n"
                    f"Estimated *max* time remaining: {minutes_left} min"
                )
            else:
                msg = "🛑 Stop command received.\nNo open trades. Bot will stop shortly."

            send_telegram_message(msg, force=True, parse_mode="")
            log("Stop command received.", level="INFO")

        elif text == "/shutdown":
            state["shutdown"] = True
            state["stopping"] = True  # Гарантируем, что новые сделки не откроются
            save_state(state)
            send_telegram_message(
                "Shutdown initiated. Waiting for positions to close...", force=True, parse_mode=""
            )
            log("Shutdown command received. Stopping flag also set to True.", level="INFO")

        elif text == "/cancel_stop":
            state = load_state()

            if not state.get("stopping"):
                send_telegram_message("ℹ️ Stop flag is not active. Nothing to cancel.", force=True)
                return

            state["stopping"] = False
            save_state(state)

            send_telegram_message(
                "✅ Stop process cancelled.\nBot will continue running.", force=True, parse_mode=""
            )
            log("Stop process cancelled via /cancel_stop command.", level="INFO")

        elif text == "/resume_after_ip":
            if DRY_RUN:
                send_telegram_message(
                    "ℹ️ /resume_after_ip is only for REAL_RUN mode.", force=True, parse_mode=""
                )
                log("Resume after IP ignored: DRY_RUN mode active.", level="INFO")
            else:
                state = load_state()
                if state.get("stopping"):
                    state["stopping"] = False
                    save_state(state)
                    send_telegram_message(
                        "✅ Bot resumed after IP change verification.", force=True, parse_mode=""
                    )
                    log("Bot resumed via /resume_after_ip command.", level="INFO")
                else:
                    send_telegram_message(
                        "ℹ️ Bot is not stopped due to IP change.", force=True, parse_mode=""
                    )
                    log("Resume command ignored: bot not stopping.", level="INFO")

        elif text == "/mode":
            score = round(get_aggressiveness_score(), 2)
            if score >= 3.5:
                bias = "🔥 HIGH"
            elif score >= 2.5:
                bias = "⚡ MODERATE"
            else:
                bias = "🧊 LOW"

            msg = (
                f"🎯 *Strategy Bias*: {bias}\n"
                f"📈 *Aggressiveness Score*: `{score}`\n"
                f"_Calculated from winrate, recent PnL, and volatility_"
            )
            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
            log(f"Mode command: bias={bias}, score={score}", level="INFO")

        elif text == "/open":
            try:
                if DRY_RUN:
                    open_positions = [
                        f"{trade['symbol']} - {trade['side'].upper()} {trade['qty']} @ {trade['entry']}"
                        for trade in trade_manager._trades.values()
                    ]
                    msg = (
                        "Open DRY Positions:\n" + "\n".join(open_positions)
                        if open_positions
                        else "No open DRY positions."
                    )
                else:
                    positions = get_cached_positions()
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
                send_telegram_message(msg, force=True, parse_mode="")
                log("Fetched open positions via /open command.", level="INFO")
            except Exception as e:
                error_msg = f"Failed to fetch open positions: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")

        elif text == "/last":
            try:
                df = pd.read_csv(EXPORT_PATH)
                if df.empty:
                    send_telegram_message("No trades logged yet.", force=True, parse_mode="")
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
                    send_telegram_message(msg, force=True, parse_mode="")
                    log("Fetched last trade via /last command.", level="INFO")
            except Exception as e:
                error_msg = f"Failed to read last trade: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")

        elif text == "/balance":
            try:
                balance = get_cached_balance()
                send_telegram_message(
                    f"Balance: {round(balance, 2)} USDC", force=True, parse_mode=""
                )
                log(
                    f"Fetched balance: {round(balance, 2)} USDC via /balance command.", level="INFO"
                )
            except Exception as e:
                error_msg = f"Failed to fetch balance: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")

        elif text == "/panic":
            state["last_command"] = "/panic"
            send_telegram_message("Confirm PANIC close by replying YES", force=True, parse_mode="")
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
                    send_telegram_message(msg, force=True, parse_mode="")
                    log("Panic close executed successfully.", level="INFO")
                else:
                    send_telegram_message("No open positions to close.", force=True, parse_mode="")
                    log("No open positions to close during panic.", level="INFO")
            except Exception as e:
                error_msg = f"Panic failed: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")
            finally:
                state["last_command"] = None
                save_state(state)

        elif text == "/status":
            try:
                current_time = now()
                last_sig = get_last_signal_time()
                idle = f"{(current_time - last_sig).seconds // 60} min ago" if last_sig else "N/A"
                balance = get_cached_balance()
                mode = (
                    "AGGRESSIVE"
                    if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD
                    else "SAFE"
                )
                stopping = "Stopping after trades" if state.get("stopping") else "Running"
                open_syms = [
                    p["symbol"] for p in get_cached_positions() if float(p.get("contracts", 0)) > 0
                ]
                msg = (
                    "<b>Bot Status</b>\n"
                    f"- Balance: {round(balance, 2)} USDC\n"
                    f"- Mode: {mode}\n"
                    f"- API Errors: {trade_stats.get('api_errors', 0)}\n"
                    f"- Last Signal: {idle}\n"
                    f"- Status: {stopping}\n"
                    f"- Open: {', '.join(open_syms) if open_syms else 'None'}"
                )
                send_telegram_message(msg, force=True, parse_mode="HTML")
                log("Fetched bot status via /status command.", level="INFO")
            except Exception as e:
                error_msg = f"Status error: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")


def handle_stop():
    state = load_state()
    if state.get("stopping"):
        send_telegram_message("⚠️ Bot is already stopping...", force=True, parse_mode="")
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
    send_telegram_message(msg, force=True, parse_mode="")
    log("Stop initiated due to IP change.", level="INFO")
