# telegram_commands.py

import time
from threading import Lock

import pandas as pd

from config import (
    DRY_RUN,
    EXPORT_PATH,
    LOG_LEVEL,
    trade_stats,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange  # Исправляем utils.core на core.exchange_init
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
            if DRY_RUN:
                send_telegram_message(
                    "Heatmap unavailable in DRY_RUN mode.", force=True, parse_mode=""
                )
                log("Heatmap request denied: DRY_RUN mode active.", level="INFO")
            else:
                generate_score_heatmap(days=7)
                log("Generated score heatmap via /heatmap command.", level="INFO")

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

            if DRY_RUN:
                from core.trade_engine import trade_manager

                open_trades = list(trade_manager._trades.values())
            else:
                open_trades = state.get("open_trades", [])

            if open_trades:
                now_ts = time.time()
                max_timeout = max(t.get("timeout_timestamp", now_ts) for t in open_trades)
                minutes_left = max(0, int((max_timeout - now_ts) / 60))

                symbols = [t.get("symbol", "?") for t in open_trades]
                msg = (
                    f"🛑 Stop command received.\n"
                    f"Waiting for {len(open_trades)} open trades to close.\n"
                    f"Pairs: {', '.join(symbols)}\n"
                    f"Estimated *max* time remaining: {minutes_left} min"
                )
            else:
                msg = "🛑 Stop command received.\nNo open trades. Bot will stop shortly."

            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
            log("Stop command received.", level="INFO")

        elif text == "/shutdown":
            import config

            config.RUNNING = False  # 🔁 Триггер graceful shutdown
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
                send_telegram_message(
                    "ℹ️ Stop flag is not active. Nothing to cancel.", force=True, parse_mode=""
                )
                log("Cancel stop ignored: stop flag was not active.", level="WARNING")
                return

            state["stopping"] = False
            save_state(state)

            # Вывод открытых сделок
            try:
                positions = get_cached_positions()
                open_syms = [p["symbol"] for p in positions if float(p.get("contracts", 0)) > 0]
                trade_info = (
                    f"\nOpen trades: {', '.join(open_syms)}" if open_syms else "\nNo open trades."
                )
            except Exception as e:
                trade_info = f"\n⚠️ Could not fetch open trades: {str(e)}"

            send_telegram_message(
                f"✅ Stop process cancelled.\nBot will continue running.{trade_info}",
                force=True,
                parse_mode="",
            )
            log("Stop process cancelled via /cancel_stop command.", level="INFO")

        elif text == "/resume_after_ip":
            state = load_state()

            if DRY_RUN:
                if state.get("stopping"):
                    state["stopping"] = False
                    save_state(state)
                    send_telegram_message(
                        "✅ DRY_RUN: Stop canceled after IP change. Resuming simulation...",
                        force=True,
                    )
                    log(
                        "Resume after IP accepted in DRY_RUN mode: flag 'stopping' removed.",
                        level="INFO",
                    )
                else:
                    send_telegram_message("DRY_RUN: Bot is already running.", force=True)
                    log("Resume ignored: no stopping flag set in DRY_RUN mode.", level="INFO")
                return

            if not state.get("stopping"):
                send_telegram_message("ℹ️ Bot is already running. No need to resume.", force=True)
                log("Resume ignored: bot not in stopping state.", level="INFO")
                return

            state["stopping"] = False
            save_state(state)
            send_telegram_message(
                "✅ Resumed after IP change. Bot will continue trading.", force=True
            )
            log("Bot resumed after IP change via /resume_after_ip command.", level="INFO")

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
                    # Local import here:
                    from core.trade_engine import trade_manager

                    open_trades = {
                        sym: t
                        for sym, t in trade_manager._trades.items()
                        if not t.get("tp1_hit")
                        and not t.get("tp2_hit")
                        and not t.get("soft_exit_hit")
                    }
                    open_positions = [
                        f"{t['symbol']} - {t['side'].upper()} {round(t['qty'], 3)} @ {round(t['entry'], 4)}"
                        for t in open_trades.values()
                    ]
                    msg = (
                        "Open DRY Positions:\n" + "\n".join(open_positions)
                        if open_positions
                        else "No open DRY positions."
                    )
                else:
                    positions = get_cached_positions()
                    open_positions = [
                        f"{p['symbol']} - {p['side'].upper()} {round(float(p['contracts']), 3)} @ {round(float(p['entryPrice']), 4)}"
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
                        f"{'[DRY_RUN MODE]\\n' if DRY_RUN else ''}"
                        f"Last Trade:\n"
                        f"{last['Symbol']} - {last['Side']}\n"
                        f"Entry: {round(last['Entry Price'], 4)}, Exit: {round(last['Exit Price'], 4)}\n"
                        f"PnL: {round(last['PnL (%)'], 2)}% ({last['Result']})\n"
                        f"Held: {round(last['Held (min)'], 1)} min"
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
                balance = round(float(balance), 2)
                send_telegram_message(f"💰 Balance: {balance} USDC", force=True, parse_mode="")
                log(f"Fetched balance: {balance} USDC via /balance command.", level="INFO")
            except Exception as e:
                error_msg = f"Failed to fetch balance: {str(e)}"
                send_telegram_message(error_msg, force=True, parse_mode="")
                log(error_msg, level="ERROR")

        elif text == "/panic":
            state["last_command"] = "/panic"
            save_state(state)
            send_telegram_message(
                "⚠️ Confirm *PANIC CLOSE* by replying `YES`", force=True, parse_mode="MarkdownV2"
            )
            log("Panic command received, awaiting confirmation.", level="WARNING")

        elif text.upper() == "YES" and state.get("last_command") == "/panic":
            try:
                positions = exchange.fetch_positions()
                closed = []
                for p in positions:
                    qty = float(p.get("contracts", 0))
                    if qty > 0:
                        side = "sell" if p["side"] == "long" else "buy"
                        exchange.create_market_order(p["symbol"], side, qty)
                        closed.append(f"{p['symbol']} ({p['side'].upper()}, {round(qty, 3)})")
                if closed:
                    msg = "🚨 *Panic Close Executed*:\n" + "\n".join(closed)
                    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
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
                balance = round(float(get_cached_balance()), 2)
                score = round(get_aggressiveness_score(), 2)

                if score >= 3.5:
                    mode = "🔥 HIGH"
                elif score >= 2.5:
                    mode = "⚡ MODERATE"
                else:
                    mode = "🧊 LOW"

                if state.get("shutdown"):
                    status = "🔌 Shutdown in progress"
                elif state.get("stopping"):
                    open_syms = [
                        p["symbol"]
                        for p in get_cached_positions()
                        if float(p.get("contracts", 0)) > 0
                    ]
                    if open_syms:
                        status = f"🛑 Stopping after trades ({len(open_syms)} open)"
                    else:
                        status = "🛑 Stopping — no open trades"
                else:
                    status = "✅ Running"

                open_syms = [
                    p["symbol"] for p in get_cached_positions() if float(p.get("contracts", 0)) > 0
                ]

                msg = (
                    "<b>Bot Status</b>\n"
                    f"- Balance: {balance} USDC\n"
                    f"- Aggressiveness: {mode} ({score})\n"
                    f"- API Errors: {trade_stats.get('api_errors', 0)}\n"
                    f"- Last Signal: {idle}\n"
                    f"- Status: {status}\n"
                    f"- Open Positions: {', '.join(open_syms) if open_syms else 'None'}"
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
        send_telegram_message("⚠️ Bot is already stopping...", force=True)
        log("Stop request ignored: bot is already stopping.", level="WARNING")
        return

    state["stopping"] = True
    save_state(state)

    if DRY_RUN:
        from core.trade_engine import trade_manager

        open_trades = list(trade_manager._trades.values())
    else:
        open_trades = state.get("open_trades", [])

    if open_trades:
        now_ts = time.time()
        max_timeout = max(t.get("timeout_timestamp", now_ts) for t in open_trades)
        minutes_left = max(0, int((max_timeout - now_ts) / 60))

        symbols = [t.get("symbol", "?") for t in open_trades]
        msg = (
            f"🛑 Stop initiated due to IP change.\n"
            f"Waiting for {len(symbols)} open trades to close.\n"
            f"Pairs: {', '.join(symbols)}\n"
            f"Estimated *max* time remaining: {minutes_left} min"
        )
    else:
        msg = "🛑 Stop initiated due to IP change.\nNo open trades. Bot will stop shortly."

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log("Stop initiated due to IP change.", level="INFO")
