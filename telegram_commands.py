import pandas as pd
import json
import os
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
    escape_markdown_v2,
    now,
    get_last_signal_time,
)


def handle_telegram_command(message, state):
    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id", 0)

    if "last_command" not in state:
        state["last_command"] = None

    if text == "/help":
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
            "📋 /debuglog - Show last 50 logs\n"
            "🔗 /pairstoday - Show active symbols today"
        )
        send_telegram_message(escape_markdown_v2(message), force=True)

    elif text == "/summary":
        summary = generate_summary()
        send_telegram_message(summary, force=True)  # No need to escape again

    elif text == "/pause":
        state["pause"] = True
        send_telegram_message("Trading paused.", force=True)

    elif text == "/resume":
        state["pause"] = False
        send_telegram_message("Trading resumed.", force=True)

    elif text == "/stop":
        state["stopping"] = True
        send_telegram_message("Bot will stop after all positions close.", force=True)

    elif text == "/shutdown":
        state["shutdown"] = True
        send_telegram_message(
            "Shutdown initiated. Waiting for positions to close...", force=True
        )

    elif text == "/mode":
        mode = "AGGRESSIVE" if is_aggressive else "SAFE"
        send_telegram_message(f"Current mode: {mode}", force=True)

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
        except Exception as e:
            send_telegram_message(
                f"Failed to fetch open positions: {str(e)}", force=True
            )

    elif text == "/last":
        try:
            df = pd.read_csv(EXPORT_PATH)
            if df.empty:
                send_telegram_message("No trades logged yet.", force=True)
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
        except Exception as e:
            send_telegram_message(f"Failed to read last trade: {str(e)}", force=True)

    elif text == "/balance":
        try:
            balance = exchange.fetch_balance()["total"]["USDC"]
            send_telegram_message(f"Balance: {round(balance, 2)} USDC", force=True)
        except Exception as e:
            send_telegram_message(f"Failed to fetch balance: {str(e)}", force=True)

    elif text == "/panic":
        state["last_command"] = "/panic"
        send_telegram_message("Confirm PANIC close by replying YES", force=True)

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
            else:
                send_telegram_message("No open positions to close.", force=True)
        except Exception as e:
            send_telegram_message(f"Panic failed: {str(e)}", force=True)
        finally:
            state["last_command"] = None

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
        except Exception as e:
            send_telegram_message(f"Status error: {str(e)}", force=True)

    elif text == "/log":
        send_daily_report()

    elif text == "/debuglog":
        if DRY_RUN and VERBOSE:
            logs = get_recent_logs()
            msg = f"Debug Log (last {len(logs.splitlines())} lines):\n\n{logs[:4000]}"
            send_telegram_message(escape_markdown_v2(msg), force=True)
        else:
            send_telegram_message(
                "Debug log only available in DRY_RUN + VERBOSE mode.", force=True
            )

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
        except Exception as e:
            send_telegram_message(f"Failed to load symbol list: {str(e)}", force=True)
