# telegram_commands.py
"""
Telegram command handlers for BinanceBot
All commands use @register_command(...), each with a category.
"""

import os
import time
from threading import Lock, Thread

from common.config_loader import (
    DRY_RUN,
)
from common.leverage_config import LEVERAGE_MAP
from core.exchange_init import exchange
from core.trade_engine import close_real_trade, trade_manager
from ip_monitor import (
    cancel_router_reboot_mode,
    enable_router_reboot_mode,
    force_ip_check_now,
    get_ip_status_message,
)
from stats import send_daily_report
from telegram.registry import COMMAND_REGISTRY
from telegram.telegram_handler import handle_errors
from telegram.telegram_utils import (
    escape_markdown_v2,
    register_command,
    send_telegram_message,
)
from utils_core import (
    get_cached_balance,
    get_runtime_config,
    save_state,
)
from utils_logging import get_recent_logs, log

command_lock = Lock()


# ---------------------------------------------------------------------
#  Helpers: formatting positions, monitoring stop timeouts
# ---------------------------------------------------------------------


def _format_pos_real(p):
    """Format REAL position info for Telegram (symbol, qty, entry, notional)."""
    try:
        symbol_raw = p.get("symbol", "")
        symbol = escape_markdown_v2(symbol_raw)
        qty = float(p.get("contracts", 0))
        entry = float(p.get("entryPrice", 0))
        side = p.get("side", "").upper()

        # По умолчанию возьмём левередж из LEVERAGE_MAP или 1
        leverage = int(p.get("leverage", LEVERAGE_MAP.get(symbol_raw, 1))) or 1

        if not qty or not entry:
            return f"{symbol} ({side}, 0.000) @ 0.00 (Lev: {leverage}x)"

        notional = qty * entry
        margin = notional / leverage

        return f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} ≈ {notional:.2f} USDC " f"(Lev: {leverage}x, Margin: {margin:.2f})"
    except Exception as e:
        log(f"Error formatting real position: {e}", level="ERROR")
        return f"{p.get('symbol', 'Unknown')} (Error)"


def _format_pos_dry(t):
    """Format DRY_RUN trade for Telegram display with enhanced error handling."""
    try:
        symbol_raw = t.get("symbol", "")
        symbol = escape_markdown_v2(symbol_raw)
        side = t.get("side", "").upper()
        qty = float(t.get("qty", 0))
        entry = float(t.get("entry", 0))
        leverage = LEVERAGE_MAP.get(symbol_raw, 5)

        if not qty or not entry:
            return f"{symbol} ({side}, 0.000) @ 0.00 (Lev: {leverage}x)"

        notional = qty * entry
        margin = notional / leverage

        return f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} ≈ {notional:.2f} USDC (Lev: {leverage}x, Margin: {margin:.2f})"

    except Exception as e:
        log(f"Error formatting DRY position: {e}", level="ERROR")
        return f"{t.get('symbol', 'Unknown')} (Error)"


def _monitor_stop_timeout(reason: str, state: dict, timeout_minutes=30, stop_event=None):
    """
    Monitor stop/shutdown process with a time limit,
    re-closing positions if needed.
    """
    from core.binance_api import close_real_trade, get_open_positions
    from core.trade_engine import trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import save_state
    from utils_logging import log

    def _format_pos_real(p):
        return f"{p['symbol']} ({p.get('side', '?')}, qty={p.get('contracts', '?')})"

    def _format_pos_dry(t):
        return f"{t['symbol']} (sim, qty={t.get('qty', '?')})"

    start = time.time()
    check_interval = 60
    last_notification_time = 0
    notification_interval = 30

    from common.config_loader import DRY_RUN

    while state.get("stopping") and (time.time() - start < timeout_minutes * 60):
        try:
            if DRY_RUN:
                open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
            else:
                positions = get_open_positions()
                open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

                # Retry closing after 5 minutes
                if open_details and (time.time() - start) > 300:
                    for p in positions:
                        if float(p.get("contracts", 0)) > 0:
                            try:
                                close_real_trade(p["symbol"])
                                log(f"[Stop] Retry closing position for {p['symbol']}", level="INFO")
                            except Exception as e:
                                log(f"[Stop] Failed to close pos: {e}", level="ERROR")

            current_time = time.time()
            if current_time - last_notification_time >= notification_interval:
                if (time.time() - start) >= timeout_minutes * 60:
                    # Timeout
                    if open_details:
                        msg = (
                            f"⏰ *Stop timeout warning*.\n"
                            f"{len(open_details)} positions still open after {int((time.time()-start)//60)} min:\n" + "\n".join(open_details) + "\nUse /panic to force close."
                        )
                        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
                        log(f"[Stop] Timeout warning after {int((time.time() - start)//60)} min", level="INFO")
                    else:
                        send_telegram_message(
                            f"🛑 *{reason}*.\nAll positions closed. Bot will exit shortly.",
                            force=True,
                            parse_mode="MarkdownV2",
                        )
                        state["stopping"] = False
                        save_state(state)
                        if stop_event:
                            stop_event.set()
                        break
                elif open_details:
                    symbols = [p.split("(")[0] for p in open_details]
                    msg = f"⏳ Still waiting on {len(open_details)} positions: {', '.join(symbols)}"
                    send_telegram_message(msg, force=True)
                last_notification_time = current_time

        except Exception as e:
            log(f"[Stop Monitor] Error: {e}", level="ERROR")

        time.sleep(check_interval)

    # Final check: if not DRY_RUN
    if not DRY_RUN:
        positions = get_open_positions()
        if not any(float(p.get("contracts", 0)) > 0 for p in positions):
            send_telegram_message("✅ All positions closed.", force=True)
            state["stopping"] = False
            save_state(state)
            log("[Stop Monitor] All positions successfully closed", level="INFO")
            if stop_event:
                stop_event.set()


# ---------------------------------------------------------------------
#  Основные команды: /help, /stop, /open, /panic, /shutdown, etc.
# ---------------------------------------------------------------------


@register_command("/help", category="Справка")
@handle_errors
def cmd_help(message, state=None, stop_event=None):
    """
    Выводит список всех команд по категориям, с описаниями.
    Usage: /help [command]
    """
    from telegram.registry import COMMAND_REGISTRY

    parts = message.get("text", "").strip().split()
    if len(parts) > 1:
        specific_cmd = f"/{parts[1].lower().lstrip('/')}"
        cmd_entry = COMMAND_REGISTRY.get(specific_cmd)
        if cmd_entry:
            help_text = cmd_entry.get("help", "Без описания")
            send_telegram_message(f"ℹ️ Справка по {specific_cmd}:\n\n{help_text}", force=True)
            return True
        else:
            send_telegram_message(f"⚠️ Команда {specific_cmd} не найдена.", force=True)
            return False

    categories_order = [
        ("Управление", "🛠"),
        ("Статистика", "📊"),
        ("Конфигурация", "⚙️"),
        ("Активность", "📈"),
        ("Инструменты", "🔧"),
        ("Справка", "❓"),
        ("Прочее", "📎"),
    ]
    grouped = {}
    for cmd, info in COMMAND_REGISTRY.items():
        cat = info.get("category", "Прочее")
        grouped.setdefault(cat, []).append((cmd, info))

    help_msg = "🤖 *Список команд BinanceBot:* \n\n"
    known_cats = set()
    for cat_name, icon in categories_order:
        if cat_name not in grouped:
            continue
        known_cats.add(cat_name)
        help_msg += f"{icon} *{cat_name}*\n"
        for cmd, info in sorted(grouped[cat_name], key=lambda x: x[0]):
            desc = info.get("help", "").split("\n", 1)[0].strip() or "Без описания"
            help_msg += f"{cmd} - {desc}\n"
        help_msg += "\n"

    # прочие категории
    for cat, commands_list in grouped.items():
        if cat not in known_cats:
            help_msg += f"📎 *{cat}*\n"
            for cmd, info in sorted(commands_list, key=lambda x: x[0]):
                desc = info.get("help", "").split("\n", 1)[0].strip() or "Без описания"
                help_msg += f"{cmd} - {desc}\n"
            help_msg += "\n"

    send_telegram_message(help_msg, parse_mode="MarkdownV2", force=True)
    log("[Telegram] /help with categories sent", level="INFO")
    return True


@register_command("/stop", category="Управление")
@handle_errors
def cmd_stop(message, state=None, stop_event=None):
    """
    🛑 Останавливает бота после закрытия всех позиций.
    Usage: /stop
    """
    log("[Stop] /stop command received.", level="INFO")

    state["stopping"] = True
    save_state(state)

    if stop_event:
        stop_event.set()

    if DRY_RUN:
        open_details = []
        for t in trade_manager._trades.values():
            if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit"):
                open_details.append(_format_pos_dry(t))
    else:
        from core.binance_api import get_open_positions

        positions = get_open_positions()
        open_details = [_format_pos_real(p) for p in positions]
        for pos in positions:
            if float(pos.get("contracts", 0)) > 0:
                try:
                    close_real_trade(pos["symbol"])
                    log(f"[Stop] Closing position for {pos['symbol']}", level="INFO")
                except Exception as e:
                    log(f"[Stop] Failed to close position: {e}", level="ERROR")

    if open_details:
        msg = "🛑 *Stop command received*.\n" "Closing these positions:\n" + "\n".join(open_details) + "\nNo new trades will be opened."
        Thread(target=_monitor_stop_timeout, args=("Stop command", state, 30), daemon=True).start()
    else:
        msg = "🛑 *Stop command received*.\nNo open positions. Bot will stop shortly."
        log("[Stop] No open positions, stopping soon.", level="INFO")

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")


@register_command("/resume", category="Управление")
@handle_errors
def cmd_resume(message, state=None, stop_event=None):
    """
    ▶️ Возобновить работу бота после /stop.
    Usage: /resume
    """
    # Если в state стоит "stopping" и нет "shutdown",
    # то достаточно снять флаг stopping
    if state.get("shutdown"):
        send_telegram_message("⚠️ Bot is in shutdown mode, cannot resume.", force=True)
        log("[Resume] Attempted /resume but bot is in shutdown mode.", level="WARNING")
        return

    if not state.get("stopping"):
        send_telegram_message("Bot is already running.", force=True)
        log("[Resume] Bot already running, no action taken.", level="INFO")
        return

    state["stopping"] = False
    save_state(state)

    send_telegram_message("✅ Trading resumed. Bot will continue scanning and opening new trades.", force=True)
    log("[Resume] Bot resumed from /stop.", level="INFO")


@register_command("/open", category="Активность")
@handle_errors
def cmd_open(message, state=None, stop_event=None):
    """
    📈 Показать все открытые позиции (DRY или REAL) и их TP-потенциал.
    Usage: /open
    """
    from strategy import calculate_tp_targets

    balance = float(get_cached_balance())
    tp1_total, tp2_total = 0.0, 0.0

    if DRY_RUN:
        open_list = []
        trades = [t for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        for t in trades:
            symbol = t["symbol"]
            qty = float(t.get("qty", 0))
            entry = float(t.get("entry", 0))
            side = t.get("side", "").lower()

            tp1, tp2 = calculate_tp_targets(symbol, side, entry)
            profit1 = (tp1 - entry) * qty if side == "buy" else (entry - tp1) * qty
            profit2 = (tp2 - entry) * qty if side == "buy" else (entry - tp2) * qty
            tp1_total += profit1
            tp2_total += profit2

            pos_str = _format_pos_dry(t)
            open_list.append(f"{pos_str}\n→ TP1: +{profit1:.2f} | TP2: +{profit2:.2f}")

        header = "🔍 *Open DRY positions:*"

    else:
        open_list = []
        positions = exchange.fetch_positions()
        real_positions = [p for p in positions if float(p.get("contracts", 0)) > 0]

        for p in real_positions:
            symbol = p["symbol"]
            qty = float(p.get("contracts", 0))
            entry = float(p.get("entryPrice", 0))
            side = p.get("side", "").lower()

            tp1, tp2 = calculate_tp_targets(symbol, side, entry)
            profit1 = (tp1 - entry) * qty if side == "buy" else (entry - tp1) * qty
            profit2 = (tp2 - entry) * qty if side == "buy" else (entry - tp2) * qty
            tp1_total += profit1
            tp2_total += profit2

            pos_str = _format_pos_real(p)
            open_list.append(f"{pos_str}\n→ TP1: +{profit1:.2f} | TP2: +{profit2:.2f}")

        header = "🔍 *Open positions:*"

    if not open_list:
        send_telegram_message(f"{header} none.", force=True)
    else:
        pct1 = (tp1_total / balance * 100) if balance else 0
        pct2 = (tp2_total / balance * 100) if balance else 0

        msg = f"{header}\n\n" + "\n\n".join(open_list) + f"\n\n📊 *Total TP1:* {tp1_total:.2f} USDC ({pct1:.2f}%)\n" + f"🏆 *Total TP2:* {tp2_total:.2f} USDC ({pct2:.2f}%)"
        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

    log("Sent /open positions with potential TP/SL info.", level="INFO")


@register_command("/panic", category="Управление")
@handle_errors
def cmd_panic(message, state=None, stop_event=None):
    log("[Panic] /panic command received.", level="WARNING")
    state["stopping"] = True
    save_state(state)
    if stop_event:
        stop_event.set()

    send_telegram_message("🚨 PANIC MODE ACTIVATED! Closing all positions...", force=True)

    from core.trade_engine import handle_panic

    handle_panic(stop_event)


@register_command("/shutdown", category="Управление")
@handle_errors
def cmd_shutdown(message, state=None, stop_event=None):
    """
    🛑 Полностью завершить работу бота после закрытия всех позиций.
    Usage: /shutdown
    """

    from threading import Thread

    from common.config_loader import DRY_RUN
    from core.exchange_init import exchange
    from core.trade_engine import trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import save_state
    from utils_logging import log

    log("[Shutdown] /shutdown command received.", level="INFO")

    # ✅ Устанавливаем флаги "мягкой остановки"
    state["shutdown"] = True
    state["stopping"] = True
    save_state(state)

    try:
        # ⏳ Список активных позиций (реальных или dry-run)
        if DRY_RUN:
            open_details = [t for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            positions = exchange.fetch_positions()
            open_details = [p for p in positions if float(p.get("contracts", 0)) > 0]

        if open_details:
            msg = (
                "🛑 *Shutdown initiated*\\.\nWaiting for positions to close softly:\n"
                + "\n".join([f"{p['symbol']} ({p.get('side', '?')}, qty={p.get('contracts', '?')})" for p in open_details])
                + "\nBot will exit automatically after all are closed\\."
            )
            Thread(target=_monitor_stop_timeout, args=("Shutdown", state, 15, stop_event), daemon=True).start()
        else:
            msg = "🛑 *Shutdown initiated*\\.\nNo open positions\\. Bot will stop shortly\\."
            log("[Shutdown] No open positions. Graceful exit expected.", level="INFO")
            if stop_event:
                stop_event.set()

        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

    except Exception as e:
        send_telegram_message(f"❌ Failed to initiate shutdown: {e}", force=True)
        log(f"Shutdown error: {e}", level="ERROR")


# ---------------------------------------------------------------------
#  IP / Misc Commands (router_reboot, etc.)
# ---------------------------------------------------------------------


@register_command("/router_reboot", category="Инструменты")
@handle_errors
def cmd_router_reboot(message, state=None, stop_event=None):
    """
    🔄 Включить режим перезагрузки роутера
    Usage: /router_reboot
    """
    enable_router_reboot_mode()
    log("Router reboot mode enabled (/router_reboot).", level="INFO")
    send_telegram_message("Router reboot mode: ENABLED", force=True)


@register_command("/cancel_reboot", category="Инструменты")
@handle_errors
def cmd_cancel_reboot(message, state=None, stop_event=None):
    """
    ❎ Отменить режим перезагрузки роутера
    Usage: /cancel_reboot
    """
    cancel_router_reboot_mode()
    log("Router reboot mode cancelled (/cancel_reboot).", level="INFO")
    send_telegram_message("Router reboot mode: CANCELLED", force=True)


@register_command("/forceipcheck", category="Инструменты")
@handle_errors
def cmd_forceipcheck(message, state=None, stop_event=None):
    """
    Принудительно запустить IP-проверку
    Usage: /forceipcheck
    """
    force_ip_check_now(None)
    log("Forced IP check via /forceipcheck command.", level="INFO")
    send_telegram_message("IP check forced. See logs for details.", force=True)


@register_command("/ipstatus", category="Инструменты")
@handle_errors
def cmd_ipstatus(message, state=None, stop_event=None):
    """
    🌐 Показать текущий IP-статус и WAN-адрес
    Usage: /ipstatus
    """
    msg = get_ip_status_message()
    send_telegram_message(msg, force=True, parse_mode="HTML")
    log("Fetched IP status via /ipstatus command.", level="INFO")


@register_command("/debuglog", category="Инструменты")
@handle_errors
def cmd_debuglog(message, state=None, stop_event=None):
    """
    🪲 Отправить кусок debug-лога (только в DRY_RUN)
    Usage: /debuglog
    """
    if not DRY_RUN:
        send_telegram_message("Debug log only available in DRY_RUN mode.", force=True)
        log("Debug log request denied: not in DRY_RUN mode.", level="INFO")
        return

    logs = get_recent_logs()
    snippet = logs[:4000]
    msg = f"Debug Log (last {len(logs.splitlines())} lines):\n\n{snippet}"
    if len(logs) > 4000:
        msg += "... (truncated)"
    send_telegram_message(msg, force=True)
    log("Sent debug log via /debuglog command.", level="INFO")


@register_command("/log", category="Инструменты")
@handle_errors
def cmd_log(message, state=None, stop_event=None):
    """
    📰 Отправить отчёт за сегодня
    Usage: /log
    """
    send_daily_report(parse_mode="")
    log("Sent daily report via /log command.", level="INFO")


@register_command("/runtime", category="Конфигурация")
@handle_errors
def cmd_runtime(message, state=None, stop_event=None):
    """
    ⚙️ Показать текущий runtime_config.json
    Usage: /runtime
    """
    cfg = get_runtime_config()
    if not cfg:
        send_telegram_message("⚠️ Runtime config is empty.", force=True)
        return
    msg = "*📊 Runtime Config:*\n"
    for key, value in cfg.items():
        msg += f"`{escape_markdown_v2(str(key))}`: `{escape_markdown_v2(str(value))}`\n"
    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")
    log("Sent /runtime config values.", level="INFO")


# ---------------------------------------------------------------------
#  Статистика/Конфигурация: /signalstats, /summary, /status, /statuslog
# ---------------------------------------------------------------------


@register_command("/signalstats", category="Статистика")
@handle_errors
def cmd_signalstats(message, state=None, stop_event=None):
    """
    📊 Показать статистику компонентов (успехи/отказы)
    """
    import json

    path = "data/component_tracker_log.json"
    if not os.path.exists(path):
        send_telegram_message("component_tracker_log.json not found.", force=True)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        stats = {}
        for sym, info in data.items():
            comps = info.get("components", {})
            for comp, success in comps.items():
                if comp not in stats:
                    stats[comp] = {"total": 0, "success": 0}
                stats[comp]["total"] += 1
                if success:
                    stats[comp]["success"] += 1

        msg = "*📊 Component Success Rate:*\n"
        for comp, s in stats.items():
            rate = 100.0 * s["success"] / s["total"] if s["total"] else 0
            msg += f"`{comp}`: {rate:.1f}% ({s['success']}/{s['total']})\n"

        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /signalstats error: {e}", force=True)


@register_command("/summary", category="Статистика")
@handle_errors
def cmd_summary(message, state=None, stop_event=None):
    """
    📊 Общий обзор состояния бота и списка пар
    """
    import json

    from utils_core import get_runtime_config

    try:
        with open("data/dynamic_symbols.json", encoding="utf-8") as f:
            pairs = json.load(f)

        cfg = get_runtime_config()
        balance = cfg.get("balance", "?")
        min_dyn = cfg.get("min_dynamic_pairs", "?")
        max_dyn = cfg.get("max_dynamic_pairs", "?")
        relax = cfg.get("relax_factor", "?")

        # Если pairs — список словарей: symbol = item["symbol"]
        symbol_count = len(pairs)

        msg = "*📊 Bot Summary*\n" f"• Active Pairs: `{symbol_count}`\n" f"• Relax Factor: `{relax}`\n" f"• Min/Max Dynamic: `{min_dyn}/{max_dyn}`\n" f"• Balance: `{balance}` USDC"
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ Failed to generate summary: {e}", force=True)


@register_command("/status", category="Статистика")
@handle_errors
def cmd_status(message, state=None, stop_event=None):
    """
    📋 Текущий режим, баланс и риск
    """
    from common.config_loader import DRY_RUN
    from utils_core import get_cached_balance, get_runtime_config

    try:
        balance_now = float(get_cached_balance())
        cfg = get_runtime_config()
        max_pos = cfg.get("max_concurrent_positions", "?")
        risk = cfg.get("risk_multiplier", 1.0)
        mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"

        msg = "*🤖 Bot Status*\n" f"• Mode: `{mode}`\n" f"• Balance: `{balance_now:.2f}` USDC\n" f"• Max Positions: `{max_pos}`\n" f"• Risk Multiplier: `{risk}`"
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ Error in /status: {e}", force=True)


@register_command("/statuslog", category="Статистика")
@handle_errors
def cmd_statuslog(message, state=None, stop_event=None):
    """
    📄 Краткий лог последнего сканирования (debug_monitoring_summary.json)
    """
    import json
    import os
    from datetime import datetime

    path = "data/debug_monitoring_summary.json"
    if not os.path.exists(path):
        send_telegram_message("No debug_monitoring_summary.json found.", force=True)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            dbg = json.load(f)

        ts = dbg.get("timestamp", "")
        dt_str = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"
        total = dbg.get("total_symbols", 0)
        passed = dbg.get("passed", 0)
        filtered = dbg.get("filtered", 0)
        near = dbg.get("near_signals", [])

        msg = f"*{dt_str}*\n" f"• Total: `{total}` | Passed: `{passed}` | Filtered: `{filtered}`\n" f"• Near signals: `{', '.join(near) if near else 'None'}`"
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /statuslog error: {e}", force=True)


@register_command("/signalconfig", category="Конфигурация")
@handle_errors
def cmd_signalconfig(message, state=None, stop_event=None):
    """
    ⚙️ Текущие ATR, Volume, relax_factor и т.п.
    """
    try:
        from utils_core import get_runtime_config

        cfg = get_runtime_config()

        relax = cfg.get("relax_factor", "?")
        atr = cfg.get("atr_threshold_percent", "?")
        vol = cfg.get("volume_threshold_usdc", "?")

        msg = "*Current Signal Config*\n" f"`Relax Factor`: `{relax}`\n" f"`ATR %`: `{atr}`\n" f"`Volume USDC`: `{vol}`"
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /signalconfig error: {e}", force=True)


@register_command("/pairstoday", category="Инструменты")
@handle_errors
def cmd_pairstoday(message, state=None, stop_event=None):
    """
    📊 Показать текущие активные пары (fixed / dynamic).
    Usage: /pairstoday
    """
    import json

    from common.config_loader import FIXED_PAIRS

    try:
        with open("data/dynamic_symbols.json", "r", encoding="utf-8") as f:
            pairs = json.load(f)

        fixed = [p for p in pairs if p in FIXED_PAIRS]
        dynamic = [p for p in pairs if p not in FIXED_PAIRS]

        msg = (
            "<b>📊 Active Pairs Today</b>\n"
            f"Total: <b>{len(pairs)}</b>\n\n"
            f"<b>📌 Fixed:</b> {', '.join([p.split('/')[0] for p in fixed]) or 'None'}\n"
            f"<b>⚡ Dynamic:</b> {', '.join([p.split('/')[0] for p in dynamic]) or 'None'}"
        )

        send_telegram_message(msg, force=True, parse_mode="HTML")
    except Exception as e:
        send_telegram_message(f"❌ /pairstoday error: {e}", force=True)


# ---------------------------------------------------------------------
# /rejections: без `score=...` (если в entry_log.csv поля score нет)
# ---------------------------------------------------------------------


@register_command("/rejections", category="Инструменты")
@handle_errors
def cmd_rejections(message, state=None, stop_event=None):
    """
    ⚠️ Последние причины отказов (из entry_log.csv)
    """
    import csv
    import os

    path = "data/entry_log.csv"
    if not os.path.exists(path):
        send_telegram_message("📭 No entry_log.csv found. No rejections logged yet.", force=True)
        return

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if not rows:
        send_telegram_message("✅ No rejections found.", force=True)
        return

    # Возьмём последние 10
    rows = sorted(rows, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]

    msg = "⚠️ *Recent Rejections:*\n\n"
    for r in rows:
        ts = r.get("timestamp", "")[:19]
        sym = r.get("symbol", "???")
        reasons = r.get("reasons", "")

        # Если поле "score" отсутствует — убираем
        # or, if you do have it:
        # sc = r.get("score", "")
        # msg += f"{ts} | {sym} | score={sc}\nreasons: {reasons}\n\n"

        # Вариант без score:
        msg += f"{ts} | {sym}\nreasons: {reasons}\n\n"

    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    log("Sent /rejections info from entry_log.csv", level="INFO")


# ---------------------------------------------------------------------
#  Main Command Handler
# ---------------------------------------------------------------------


def handle_telegram_command(message, state, stop_event=None):
    """
    Главный обработчик Telegram-команд:
    ищет команды в COMMAND_REGISTRY (через @register_command),
    иначе - "неизвестная команда".
    """
    log(f"All registered commands: {list(COMMAND_REGISTRY.keys())}", level="DEBUG")

    msg_date = message.get("date", 0)
    session_start = state.get("session_start_time", 0)
    if msg_date and session_start and msg_date < session_start:
        log(f"Ignoring stale command from previous session: {message.get('text', '')}", level="DEBUG")
        return

    text = message.get("text", "").strip().lower()
    log(f"Received command: {text}", level="DEBUG")

    # 1) Exact match
    if text in COMMAND_REGISTRY:
        cmd_entry = COMMAND_REGISTRY[text]
        try:
            cmd_entry["handler"](message, state, stop_event)
        except Exception as e:
            log(f"[Telegram] Error in {text}: {e}", level="ERROR")
            send_telegram_message(f"❌ Error: {e}", force=True)
        return

    # 2) Possibly command + arguments (/open 5)
    base = text.split()[0]
    for cmd_text, cmd_info in COMMAND_REGISTRY.items():
        if base == cmd_text:
            try:
                cmd_info["handler"](message, state, stop_event)
            except Exception as e:
                log(f"[Telegram] Error in {base}: {e}", level="ERROR")
                send_telegram_message(f"❌ Error: {e}", force=True)
            return

    # 3) Not found
    send_telegram_message("Command not recognized. Try /help", force=True)
    log(f"Command not recognized: {text}", level="INFO")
