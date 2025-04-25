import time
from threading import Lock, Thread

import pandas as pd

from config import DRY_RUN, EXPORT_PATH, LEVERAGE_MAP, LOG_LEVEL, trade_stats
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.trade_engine import trade_manager  # Added import for trade_manager
from score_heatmap import generate_score_heatmap
from stats import generate_summary
from telegram.telegram_ip_commands import handle_ip_and_misc_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, get_last_signal_time, load_state, save_state
from utils_logging import log, now

command_lock = Lock()


# --- Helpers ------------------------------------------------------------
def _format_pos_real(p):
    symbol = escape_markdown_v2(p.get("symbol", ""))
    qty = float(p.get("contracts", 0))
    entry = float(p.get("entryPrice", 0))
    side = p.get("side", "").upper()
    leverage = int(p.get("leverage", LEVERAGE_MAP.get(p.get("symbol", ""), 1))) or 1
    if not qty or not entry:
        return f"{symbol} ({side}, 0.000) @ 0.00 = ~0.00 USDC (Leverage: {leverage}x, Margin: ~0.00 USDC)"
    notional = qty * entry
    margin = notional / leverage
    return (
        f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} = ~{notional:.2f} USDC "
        f"(Leverage: {leverage}x, Margin: ~{margin:.2f} USDC)"
    )


def _format_pos_dry(t):
    symbol = escape_markdown_v2(t.get("symbol", ""))
    side = t.get("side", "").upper()
    qty = float(t.get("qty", 0))
    entry = float(t.get("entry", 0))
    leverage = LEVERAGE_MAP.get(t.get("symbol", ""), 5)
    if not qty or not entry:
        return f"{symbol} ({side}, 0.000) @ 0.00 = ~0.00 USDC (Leverage: {leverage}x, Margin: ~0.00 USDC)"
    notional = qty * entry
    margin = notional / leverage
    return (
        f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} = ~{notional:.2f} USDC "
        f"(Leverage: {leverage}x, Margin: ~{margin:.2f} USDC)"
    )


def _monitor_stop_timeout(reason, state, timeout_minutes=30):
    start = time.time()
    while state.get("stopping"):
        if time.time() - start >= timeout_minutes * 60:
            if DRY_RUN:
                open_details = [
                    _format_pos_dry(t)
                    for t in trade_manager._trades.values()
                    if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
                ]
            else:
                try:
                    positions = exchange.fetch_positions()
                    open_details = [
                        _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
                    ]
                except Exception as e:
                    log(f"[Stop Timeout] Failed fetch: {e}", level="ERROR")
                    send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
                    open_details = []
            if open_details:
                msg = (
                    "⏰ *Stop timeout warning*.\n"
                    f"{len(open_details)} positions still open after {int((time.time() - start) // 60)} minutes:\n"
                    + "\n".join(open_details)
                    + "\nUse /panic YES to force close."
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
        time.sleep(60)


def _initiate_stop(reason):
    state = load_state()
    if state.get("stopping"):
        send_telegram_message("⚠️ Bot is already stopping…", force=True)
        return False
    state["stopping"] = True
    save_state(state)

    if DRY_RUN:
        open_details = [
            _format_pos_dry(t)
            for t in trade_manager._trades.values()
            if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
        ]
    else:
        try:
            positions = exchange.fetch_positions()
            open_details = [
                _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
            ]
        except Exception as e:
            log(f"[Stop] Failed to fetch positions: {e}", level="ERROR")
            send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
            open_details = []

    if open_details:
        msg = (
            f"🛑 *{escape_markdown_v2(reason)}*.\n"
            "Waiting for these positions to close:\n"
            + "\n".join(open_details)
            + "\nNo new trades will be opened."
        )
        Thread(target=_monitor_stop_timeout, args=(reason, state), daemon=True).start()
    else:
        msg = f"🛑 {reason}.\nNo open positions. Bot will stop shortly."

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log(f"[Stop] {reason}", level="INFO")
    return True


def handle_stop_command():
    state = load_state()
    state["stopping"] = True
    save_state(state)

    if DRY_RUN:
        open_details = [
            _format_pos_dry(t)
            for t in trade_manager._trades.values()
            if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
        ]
    else:
        try:
            positions = exchange.fetch_positions()
            open_details = [
                _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
            ]
        except Exception as e:
            log(f"[Stop] Failed to fetch positions: {e}", level="ERROR")
            send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
            open_details = []

    if open_details:
        msg = (
            "🛑 *Stop command received*.\n"
            "Closing the following positions:\n"
            + "\n".join(open_details)
            + "\nNo new trades will be opened."
        )
    else:
        msg = "🛑 *Stop command received*.\nNo open positions. Bot will stop shortly."

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log("[Stop] Stop command processed.", level="INFO")


def handle_panic_command(message, state):
    text = message.get("text", "").strip().lower()
    if text == "/panic":
        # Show positions that will be closed
        if DRY_RUN:
            open_details = [
                _format_pos_dry(t)
                for t in trade_manager._trades.values()
                if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
            ]
        else:
            try:
                positions = exchange.fetch_positions()
                open_details = [
                    _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
                ]
            except Exception as e:
                log(f"[Panic] Failed to fetch positions: {e}", level="ERROR")
                send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
                open_details = []

        state["last_command"] = "/panic"
        save_state(state)
        msg = (
            "⚠️ Confirm *PANIC CLOSE* by replying `YES`...\n"
            f"Positions to close ({len(open_details)}):\n"
            + ("\n".join(open_details) if open_details else "None")
        )
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        log("Panic command initiated, awaiting YES confirmation.", level="INFO")
        return

    if text.upper() == "YES" and state.get("last_command") == "/panic":
        try:
            from core.trade_engine import handle_panic
            from main import stop_event  # Импортируем stop_event здесь

            handle_panic(stop_event)  # Передаём stop_event
        except Exception as e:
            send_telegram_message(f"Panic failed: {e}", force=True)
            log(f"Panic error: {e}", level="ERROR")
        finally:
            state["last_command"] = None
            save_state(state)


# -----------------------------------------------------------------------


def handle_telegram_command(message, state):
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
                "🔄 /router_reboot - Plan router reboot\n"
                "▶️ /resume_after_ip - Resume after IP change\n"
                "🚪 /shutdown - Exit bot after positions close\n"
                "🛑 /stop - Stop after all positions close\n"
                "🚨 /panic - Force close all trades (confirmation)\n"
                "🔍 /status - Show bot status\n"
                "📊 /summary - Show performance summary"
            )
            send_telegram_message(help_msg, force=True, parse_mode="")
            if LOG_LEVEL == "DEBUG":
                log("Sent help message.", level="DEBUG")
        elif text == "/summary":
            summary = generate_summary()
            if DRY_RUN:
                open_details = [
                    _format_pos_dry(t)
                    for t in trade_manager._trades.values()
                    if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
                ]
            else:
                try:
                    positions = exchange.fetch_positions()
                    open_details = [
                        _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
                    ]
                except Exception as e:
                    log(f"[Summary] Failed fetch: {e}", level="ERROR")
                    open_details = []
            msg = (
                summary
                + "\n\n*Open Positions*:\n"
                + ("\n".join(open_details) if open_details else "None")
            )
            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
            if LOG_LEVEL == "DEBUG":
                log("Sent summary via /summary.", level="DEBUG")
        elif text == "/heatmap":
            if DRY_RUN:
                send_telegram_message("Heatmap unavailable in DRY_RUN mode.", force=True)
            else:
                generate_score_heatmap(days=7)
                log("Generated heatmap.", level="INFO")
        elif text == "/stop":
            handle_stop_command()
        elif text in ("/panic", "yes"):
            handle_panic_command(message, state)
        elif text == "/shutdown":
            import config

            config.RUNNING = False
            state["shutdown"] = True
            state["stopping"] = True
            save_state(state)

            if DRY_RUN:
                open_details = [
                    _format_pos_dry(t)
                    for t in trade_manager._trades.values()
                    if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")
                ]
            else:
                try:
                    positions = exchange.fetch_positions()
                    open_details = [
                        _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
                    ]
                except Exception as e:
                    log(f"[Shutdown] Failed to fetch positions: {e}", level="ERROR")
                    send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
                    open_details = []

            if open_details:
                msg = (
                    "🛑 *Shutdown initiated*.\n"
                    "Waiting for these positions to close:\n"
                    + "\n".join(open_details)
                    + "\nBot will exit after closure."
                )
            else:
                msg = "🛑 *Shutdown initiated*.\nNo open positions. Bot will exit shortly."

            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
            log("Shutdown command received.", level="INFO")
        elif text == "/cancel_stop":
            state = load_state()
            if not state.get("stopping"):
                send_telegram_message("ℹ️ Stop flag is not active.", force=True)
                return
            state["stopping"] = False
            save_state(state)
            try:
                positions = exchange.fetch_positions() if not DRY_RUN else []
                open_syms = [p["symbol"] for p in positions if float(p.get("contracts", 0)) > 0]
                trade_info = (
                    f"\nOpen trades: {', '.join(open_syms)}" if open_syms else "\nNo open trades."
                )
            except Exception as e:
                trade_info = f"\n⚠️ Could not fetch open trades: {str(e)}"
                log(f"[Cancel Stop] Failed to fetch positions: {e}", level="ERROR")
            send_telegram_message(
                f"✅ Stop process cancelled. Bot will continue.{trade_info}", force=True
            )
            log("Stop process cancelled.", level="INFO")
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
        elif text == "/mode":
            score = round(get_aggressiveness_score(), 2)
            bias = "🔥 HIGH" if score >= 3.5 else "⚡ MODERATE" if score >= 2.5 else "🧊 LOW"
            msg = f"🎯 *Strategy Bias*: {bias}\n📈 *Score*: `{score}`"
            send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
        elif text == "/open":
            try:
                if DRY_RUN:
                    open_list = [
                        _format_pos_dry(t)
                        for t in trade_manager._trades.values()
                        if not t.get("tp1_hit")
                        and not t.get("tp2_hit")
                        and not t.get("soft_exit_hit")
                    ]
                    header = "Open DRY positions:"
                else:
                    positions = exchange.fetch_positions()
                    open_list = [
                        _format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0
                    ]
                    header = "Open positions:"
                msg = header + "\n" + "\n".join(open_list) if open_list else f"{header} none."
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent /open positions.", level="INFO")
            except Exception as e:
                err = f"Failed to fetch open positions: {e}"
                send_telegram_message(err, force=True)
                log(err, level="ERROR")
        elif text == "/last":
            try:
                df = pd.read_csv(EXPORT_PATH)
                if df.empty:
                    send_telegram_message("No trades logged yet.", force=True)
                else:
                    last = df.iloc[-1]
                    msg = (
                        f"{'[DRY_RUN]\n' if DRY_RUN else ''}Last Trade:\n"
                        f"{last['Symbol']} - {last['Side']}@{round(last['Entry Price'],4)} -> {round(last['Exit Price'],4)}\n"
                        f"PnL: {round(last['PnL (%)'],2)}% ({last['Result']})"
                    )
                    send_telegram_message(msg, force=True)
            except Exception as e:
                send_telegram_message(f"Failed to read last trade: {e}", force=True)
                log(f"Last trade error: {e}", level="ERROR")
        elif text == "/balance":
            try:
                balance = round(float(get_cached_balance()), 2)
                send_telegram_message(f"💰 Balance: {balance} USDC", force=True)
            except Exception as e:
                send_telegram_message(f"Failed to fetch balance: {e}", force=True)
                log(f"Balance error: {e}", level="ERROR")
        elif text == "/status":
            try:
                current = now()
                last_sig = get_last_signal_time()
                idle = f"{(current - last_sig).seconds//60} min ago" if last_sig else "N/A"
                balance = round(float(get_cached_balance()), 2)
                score = round(get_aggressiveness_score(), 2)
                mode = "🔥 HIGH" if score >= 3.5 else "⚡ MODERATE" if score >= 2.5 else "🧊 LOW"
                if state.get("shutdown"):
                    status = "🔌 Shutdown in progress"
                elif state.get("stopping"):
                    try:
                        positions = exchange.fetch_positions() if not DRY_RUN else []
                        open_syms = [
                            p["symbol"] for p in positions if float(p.get("contracts", 0)) > 0
                        ]
                        status = (
                            f"🛑 Stopping after trades ({len(open_syms)} open)"
                            if open_syms
                            else "🛑 Stopping — no open trades"
                        )
                    except Exception as e:
                        status = "🛑 Stopping — error fetching trades"
                        log(f"[Status] Failed to fetch positions for status: {e}", level="ERROR")
                else:
                    status = "✅ Running"
                if DRY_RUN:
                    open_details = [
                        _format_pos_dry(t)
                        for t in trade_manager._trades.values()
                        if not t.get("tp1_hit")
                        and not t.get("tp2_hit")
                        and not t.get("soft_exit_hit")
                    ]
                else:
                    try:
                        positions = exchange.fetch_positions()
                        open_details = [
                            _format_pos_real(p)
                            for p in positions
                            if float(p.get("contracts", 0)) > 0
                        ]
                    except Exception as e:
                        log(f"[Status] Failed fetch: {e}", level="ERROR")
                        send_telegram_message(f"❌ Failed to fetch positions: {e}", force=True)
                        open_details = []
                msg = (
                    "<b>Bot Status</b>\n"
                    f"- Balance: {balance} USDC\n"
                    f"- Aggressiveness: {mode} ({score})\n"
                    f"- API Errors: {trade_stats.get('api_errors',0)}\n"
                    f"- Last Signal: {idle}\n"
                    f"- Status: {status}\n"
                    f"- Open Positions:\n" + ("\n".join(open_details) if open_details else "None")
                )
                send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                log("Sent /status.", level="INFO")
            except Exception as e:
                send_telegram_message(f"Status error: {e}", force=True)
                log(f"Status error: {e}", level="ERROR")
