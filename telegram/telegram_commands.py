"""
Telegram command handlers for BinanceBot
All commands use @register_command(...), each with a category.
"""

import json
import os
import time
from threading import Lock, Thread

from common.config_loader import (
    DRY_RUN,
)
from common.leverage_config import LEVERAGE_MAP
from core.runtime_state import global_trading_pause_until, is_trading_globally_paused, paused_symbols
from core.trade_engine import close_real_trade, open_positions_count, trade_manager
from telegram.registry import COMMAND_REGISTRY
from telegram.telegram_handler import handle_errors
from telegram.telegram_utils import (
    escape_markdown_v2,
    register_command,
    send_telegram_file,
    send_telegram_message,
)
from utils_core import (
    get_cached_balance,
    get_runtime_config,
    save_state,
)
from utils_logging import log

command_lock = Lock()

# === Helpers ===


def _format_pos_real(p):
    try:
        symbol_raw = p.get("symbol", "")
        symbol = escape_markdown_v2(symbol_raw)
        qty = float(p.get("contracts", 0))
        entry = float(p.get("entryPrice", 0))
        side = p.get("side", "").upper()
        leverage = int(p.get("leverage", LEVERAGE_MAP.get(symbol_raw, 1))) or 1

        if not qty or not entry:
            return f"{symbol} ({side}, 0.000) @ 0.00 (Lev: {leverage}x)"

        notional = qty * entry
        margin = notional / leverage

        return f"{symbol} ({side}, {qty:.3f}) @ {entry:.2f} ≈ {notional:.2f} USDC (Lev: {leverage}x, Margin: {margin:.2f})"
    except Exception as e:
        log(f"Error formatting real position: {e}", level="ERROR")
        return f"{p.get('symbol', 'Unknown')} (Error)"


def _format_pos_dry(t):
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


def _monitor_stop_timeout(reason: str, state: dict, timeout_minutes=30):
    """
    Monitor stop/shutdown process with a time limit,
    re-closing positions if needed.
    """
    start = time.time()
    check_interval = 60
    last_notification_time = 0
    notification_interval = 30

    from core.binance_api import get_open_positions

    while state.get("stopping") and (time.time() - start < timeout_minutes * 60):
        try:
            if DRY_RUN:
                open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
            else:
                positions = get_open_positions()
                open_details = [_format_pos_real(p) for p in positions]

                # Retry closing after 5 minutes
                if open_details and (time.time() - start) > 300:
                    for pos in positions:
                        if float(pos.get("contracts", 0)) > 0:
                            try:
                                close_real_trade(pos["symbol"])
                                log(f"[Stop] Retry closing position for {pos['symbol']}", level="INFO")
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


@register_command("/help", category="Справка")
@handle_errors
def cmd_help(message, state=None, stop_event=None):
    """
    🤖 Показать список всех доступных команд по категориям.
    """
    from telegram.registry import COMMAND_REGISTRY

    parts = message.get("text", "").strip().split()
    if len(parts) > 1:
        specific_cmd = f"/{parts[1].lower().lstrip('/')}"
        cmd_entry = COMMAND_REGISTRY.get(specific_cmd)
        if cmd_entry:
            help_text = cmd_entry.get("help") or (cmd_entry.get("handler").__doc__ or "Без описания").strip()
            send_telegram_message(f"ℹ️ Справка по {specific_cmd}:\n\n{help_text}", force=True)
            return True
        else:
            send_telegram_message(f"⚠️ Команда {specific_cmd} не найдена.", force=True)
            return False

    categories_order = [
        ("Управление", "🛠"),
        ("Статистика", "📊"),
        ("Конфигурация", "⚙️"),
        ("Инструменты", "🔧"),
        ("Справка", "❓"),
    ]
    grouped = {}
    for cmd, info in COMMAND_REGISTRY.items():
        cat = info.get("category", "Прочее")
        grouped.setdefault(cat, []).append((cmd, info))

    help_msg = "🤖 *Список команд BinanceBot:* \n\n"
    for cat_name, icon in categories_order:
        if cat_name in grouped:
            help_msg += f"{icon} *{cat_name}*\n"
            for cmd, info in sorted(grouped[cat_name]):
                desc = info.get("description") or (info.get("handler").__doc__ or "").strip().split("\n")[0]
                help_msg += f"{cmd} - {desc or 'Без описания'}\n"
            help_msg += "\n"

    send_telegram_message(help_msg, parse_mode="MarkdownV2", force=True)


@register_command("/pause", category="Управление")
@handle_errors
def cmd_pause(message, state=None, stop_event=None):
    """
    ⏸️ Временно остановить входы вручную (глобальная пауза)
    """
    from core.runtime_state import pause_all_trading

    pause_all_trading(minutes=999999)
    send_telegram_message("⛔ *Manual pause activated.* New trades are blocked.", force=True)


@register_command("/resume", category="Управление")
@handle_errors
def cmd_resume(message, state=None, stop_event=None):
    """
    ▶️ Снять все блокировки (pause, stop, shutdown)
    Usage: /resume [force]
    """
    global global_trading_pause_until

    text = message.get("text", "").strip().lower()
    force_mode = "force" in text

    if state.get("shutdown") and not force_mode:
        send_telegram_message("⚠️ Bot is in shutdown mode. Use `/resume force` to override.", force=True)
        log("[Resume] Blocked: shutdown flag is set, and no force override.", level="WARNING")
        return

    # Снимаем все флаги
    state["stopping"] = False
    state["shutdown"] = False
    global_trading_pause_until = None
    save_state(state)

    send_telegram_message("▶️ *Trading resumed*. All restrictions lifted.", force=True)
    log("[Resume] All flags cleared (pause, stop, shutdown).", level="INFO")


@register_command("/stop", category="Управление")
@handle_errors
def cmd_stop(message, state=None, stop_event=None):
    """
    🛑 Останавливает бота после закрытия всех позиций (мягко).
    Usage: /stop
    """
    from core.binance_api import get_open_positions
    from telegram.telegram_utils import send_telegram_message
    from utils_core import save_state
    from utils_logging import log

    log("[Stop] /stop command received.", level="INFO")

    state["stopping"] = True
    save_state(state)

    if stop_event:
        stop_event.set()

    if DRY_RUN:
        open_details = [_format_pos_dry(t) for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
    else:
        positions = get_open_positions()
        open_details = [_format_pos_real(p) for p in positions if float(p.get("contracts", 0)) > 0]

    if open_details:
        msg = "🛑 *Stop command received*.\n" "Waiting for positions to close softly:\n" + "\n".join(open_details) + "\nNo new trades will be opened."
        Thread(target=_monitor_stop_timeout, args=("Stop command", state, 30), daemon=True).start()
    else:
        msg = "🛑 *Stop command received*.\nNo open positions. Bot is now paused."
        log("[Stop] No open positions, stopping soon.", level="INFO")

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")


@register_command("/shutdown", category="Управление")
@handle_errors
def cmd_shutdown(message, state=None, stop_event=None):
    """
    🛑 Полностью завершить работу бота после закрытия всех позиций.
    Usage: /shutdown
    """

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

    if stop_event:
        stop_event.set()

    try:
        # ⏳ Список активных позиций (реальных или dry-run)
        if DRY_RUN:
            open_details = [t for t in trade_manager._trades.values() if not t.get("tp1_hit") and not t.get("tp2_hit") and not t.get("soft_exit_hit")]
        else:
            positions = exchange.fetch_positions()
            open_details = [p for p in positions if float(p.get("contracts", 0)) > 0]

        if open_details:
            msg = (
                "🛑 *Shutdown initiated*.\nWaiting for positions to close softly:\n"
                + "\n".join([f"{p['symbol']} ({p.get('side', '?')}, qty={p.get('contracts', '?')})" for p in open_details])
                + "\nBot will exit automatically after all are closed."
            )
            Thread(target=_monitor_stop_timeout, args=("Shutdown", state, 15), daemon=True).start()
        else:
            msg = "🛑 *Shutdown initiated*.\nNo open positions. Bot will stop shortly."
            log("[Shutdown] No open positions. Graceful exit expected.", level="INFO")

        send_telegram_message(msg, force=True, parse_mode="MarkdownV2")

    except Exception as e:
        send_telegram_message(f"❌ Failed to initiate shutdown: {e}", force=True)
        log(f"Shutdown error: {e}", level="ERROR")


@register_command("/panic", category="Управление")
@handle_errors
def cmd_panic(message, state=None, stop_event=None):
    """
    🚨 Немедленное закрытие всех позиций
    """
    from core.trade_engine import handle_panic

    log("[Panic] /panic command received.", level="ERROR")
    state["stopping"] = True
    save_state(state)
    send_telegram_message("🚨 *Panic mode activated*. All positions will be force-closed.", force=True)
    handle_panic(stop_event)


@register_command("/logtail", category="Инструменты")
@handle_errors
def cmd_logtail(message, state=None, stop_event=None):
    """📄 Последние строки из main.log"""
    try:
        with open("main.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
        tail = lines[-25:] if len(lines) >= 25 else lines
        msg = "📄 *Log Tail (last 25 lines)*\n\n" + "".join(tail[-25:])
        send_telegram_message(msg, force=True)
    except Exception as e:
        send_telegram_message(f"❌ /logtail error: {e}", force=True)


@register_command("/ipstatus", category="Инструменты")
@handle_errors
def cmd_ipstatus(message, state=None, stop_event=None):
    """
    🌐 Показать текущий WAN IP и сетевой статус
    """
    from ip_monitor import get_ip_status_message

    try:
        msg = get_ip_status_message()
        send_telegram_message(msg, force=True, parse_mode="HTML")
    except Exception as e:
        send_telegram_message(f"❌ /ipstatus error: {e}", force=True)


@register_command("/forceipcheck", category="Инструменты")
@handle_errors
def cmd_forceipcheck(message, state=None, stop_event=None):
    """
    🛰 Принудительно запустить проверку внешнего IP
    """
    from ip_monitor import force_ip_check_now

    try:
        force_ip_check_now(stop_event)
        send_telegram_message("🛰 IP check forced. See logs for details.", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /forceipcheck error: {e}", force=True)


@register_command("/pnl_today", category="Статистика")
@handle_errors
def cmd_pnl_today(message, state=None, stop_event=None):
    """📈 PnL за сегодня (по tp_performance.csv)"""

    import pandas as pd

    try:
        df = pd.read_csv("data/tp_performance.csv", parse_dates=["timestamp"])
        today = pd.Timestamp.now().normalize()
        df_today = df[df["timestamp"] >= today]
        if df_today.empty:
            send_telegram_message("📋 No trades today.", force=True)
            return
        total = len(df_today)
        win = (df_today["result"].isin(["TP1", "TP2"])).sum()
        loss = (df_today["result"] == "SL").sum()
        avg = df_today["pnl_percent"].mean()
        msg = f"📈 *PnL Today*\nTotal Trades: {total}\nWins: {win}\nLosses: {loss}\nAvg PnL: {avg:.2f}%"
        send_telegram_message(escape_markdown_v2(msg))
    except Exception as e:
        send_telegram_message(f"❌ /pnl_today error: {e}", force=True)


@register_command("/dailycsv", category="Инструменты")
@handle_errors
def cmd_dailycsv(message, state=None, stop_event=None):
    """📄 Отправить tp_performance.csv"""
    try:
        path = "data/tp_performance.csv"
        if not os.path.exists(path):
            send_telegram_message("📭 tp_performance.csv not found.", force=True)
            return
        send_telegram_file(path, caption="📄 tp_performance.csv")
    except Exception as e:
        send_telegram_message(f"❌ /dailycsv error: {e}", force=True)


@register_command("/blockers", category="Статистика")
@handle_errors
def cmd_blockers(message, state=None, stop_event=None):
    """🚫 Символы в блоке или анти-reentry"""
    try:
        import datetime

        from core.risk_guard import symbol_blocklist, symbol_last_entry

        now = datetime.datetime.utcnow()
        msg = "*🚫 Active Blockers:*\n"
        paused = []
        for sym, until in symbol_blocklist.items():
            if until > now:
                minutes = int((until - now).total_seconds() / 60)
                paused.append(f"{sym} ({minutes}m)")
        if paused:
            msg += "• SL Pause: " + ", ".join(paused) + "\n"
        reentry = []
        for sym, ts in symbol_last_entry.items():
            age = int((now - ts).total_seconds())
            if age < 300:
                reentry.append(f"{sym} ({age}s ago)")
        if reentry:
            msg += "• Anti-reentry: " + ", ".join(reentry)
        if not paused and not reentry:
            msg = "✅ No active blockers."
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /blockers error: {e}", force=True)


@register_command("/summary", category="Статистика")
@handle_errors
def cmd_summary(message, state=None, stop_event=None):
    """📊 Сводка: пары, настройки, баланс, PnL, пауза"""
    import json

    import pandas as pd

    from core.runtime_state import global_trading_pause_until, is_trading_globally_paused

    try:
        with open("data/dynamic_symbols.json", encoding="utf-8") as f:
            pairs = json.load(f)
        cfg = get_runtime_config()
        balance = get_cached_balance()

        # Загружаем TP performance CSV
        pnl_today = 0.0
        tp1_hits = 0
        sl_hits = 0
        trade_count = 0
        try:
            df = pd.read_csv("data/tp_performance.csv", parse_dates=["Date"])
            today = pd.Timestamp.now().normalize()
            df_today = df[df["Date"] >= today]
            trade_count = len(df_today)
            tp1_hits = (df_today["TP1 Hit"] == "YES").sum()
            sl_hits = (df_today["SL Hit"] == "YES").sum()
            pnl_today = df_today["PnL (%)"].sum()
        except Exception as e:
            log(f"[Summary] CSV parse error: {e}", level="DEBUG")

        msg = (
            "*📊 Bot Summary*\n"
            f"• Active Pairs: `{len(pairs)}`\n"
            f"• Relax: `{cfg.get('relax_factor', '?')}`\n"
            f"• Min/Max Dynamic: `{cfg.get('min_dynamic_pairs', '?')}/{cfg.get('max_dynamic_pairs', '?')}`\n"
            f"• Balance: `{round(balance, 2)}` USDC\n"
            f"• Trades Today: `{trade_count}` | TP1: `{tp1_hits}` | SL: `{sl_hits}`\n"
            f"• PnL Today: `{round(pnl_today, 2)}` %\n"
        )

        # Добавим статус глобальной паузы
        if is_trading_globally_paused():
            pause_until_str = global_trading_pause_until.strftime("%H:%M:%S") if global_trading_pause_until else "?"
            msg += f"• ⛔ *Global Pause:* until `{pause_until_str}`\n"
        else:
            msg += "• ⛔ Global Pause: `inactive`\n"

        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /summary error: {e}", force=True)


@register_command("/status", category="Статистика")
@handle_errors
def cmd_status(message, state=None, stop_event=None):
    """📋 Режим, баланс, макс. позиций, риск, статус торговли"""
    try:
        from common.config_loader import DRY_RUN
        from core.runtime_state import global_trading_pause_until, is_trading_globally_paused

        balance_now = float(get_cached_balance())
        cfg = get_runtime_config()
        max_pos = cfg.get("max_concurrent_positions", "?")
        risk = cfg.get("risk_multiplier", 1.0)
        mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"

        msg = "*🤖 Bot Status*\n"
        msg += f"• Mode: `{mode}`\n"
        msg += f"• Balance: `{balance_now:.2f}` USDC\n"
        msg += f"• Max Positions: `{max_pos}`\n"
        msg += f"• Risk: `{risk}`\n"

        if is_trading_globally_paused():
            until_str = global_trading_pause_until.strftime("%H:%M:%S") if global_trading_pause_until else "?"
            msg += f"• ⛔ *Global Pause:* until `{until_str}`\n"
        else:
            msg += "• ⛔ Global Pause: `inactive`\n"

        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /status error: {e}", force=True)


@register_command("/signalstats", category="Статистика")
@handle_errors
def cmd_signalstats(message, state=None, stop_event=None):
    """📊 Компоненты: успехи / ошибки"""
    import json

    try:
        with open("data/component_tracker_log.json", encoding="utf-8") as f:
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
        msg = "*📊 Component Success:*\n"
        for comp, s in stats.items():
            rate = 100 * s["success"] / s["total"] if s["total"] else 0
            msg += f"`{comp}`: {rate:.1f}% ({s['success']}/{s['total']})\n"
        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)
    except Exception as e:
        send_telegram_message(f"❌ /signalstats error: {e}", force=True)


@register_command("/riskstatus", category="Статистика")
@handle_errors
def cmd_riskstatus(message, state=None, stop_event=None):
    """
    📊 Сводка по рискам: паузы, убытки, блоки
    """
    from core.runtime_state import (
        global_trading_pause_until,
        is_trading_globally_paused,
        paused_symbols,
    )
    from core.trade_engine import open_positions_count
    from tp_logger import get_today_pnl_from_csv

    msg = "*📊 Risk & Block Status*\n\n"

    # Global pause
    if is_trading_globally_paused():
        until = global_trading_pause_until.strftime("%H:%M") if global_trading_pause_until else "?"
        msg += f"• ⛔ Global Pause: active (until {until})\n"
    else:
        msg += "• ⛔ Global Pause: inactive\n"

    # Paused symbols
    if paused_symbols:
        items = [f"{s} (until {t.strftime('%H:%M')})" for s, t in paused_symbols.items()]
        msg += f"• 🔒 Paused Symbols: {', '.join(items)}\n"
    else:
        msg += "• 🔒 Paused Symbols: none\n"

    # Daily PnL
    try:
        pnl = get_today_pnl_from_csv()
        msg += f"• 📉 Daily PnL: {pnl:.2f} USDC\n"
    except Exception as e:
        msg += f"• 📉 Daily PnL: error ({e})\n"

    # Open positions
    msg += f"• 📈 Open Positions: {open_positions_count}\n"

    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)


@register_command("/rejections", category="Инструменты")
@handle_errors
def cmd_rejections(message, state=None, stop_event=None):
    """⚠️ Последние причины отказов"""
    import csv

    path = "data/entry_log.csv"
    if not os.path.exists(path):
        send_telegram_message("📭 No entry_log.csv found.", force=True)
        return
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = sorted(reader, key=lambda r: r.get("timestamp", ""), reverse=True)[:10]
    msg = "⚠️ *Recent Rejections:*\n\n"
    for r in rows:
        ts = r.get("timestamp", "")[:19]
        sym = r.get("symbol", "???")
        reasons = r.get("reasons", "")
        msg += f"{ts} | {sym}\nreasons: {reasons}\n\n"
    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)


@register_command("/runtime", category="Конфигурация")
@handle_errors
def cmd_runtime(message, state=None, stop_event=None):
    """⚙️ Показать текущий runtime_config.json + паузы/блокировки"""
    cfg = get_runtime_config()
    if not cfg:
        send_telegram_message("⚠️ Runtime config is empty.", force=True)
        return

    msg = "*⚙️ Runtime Config:*\n"
    for key, value in cfg.items():
        msg += f"`{escape_markdown_v2(str(key))}`: `{escape_markdown_v2(str(value))}`\n"

    # Добавим статус позиций
    msg += f"\n*📈 Open Positions:* `{open_positions_count}`\n"

    # Символы на паузе
    if paused_symbols:
        msg += "*⏸️ Symbols on Pause:*\n"
        for sym, until in paused_symbols.items():
            until_str = until.strftime("%H:%M:%S")
            msg += f"• `{escape_markdown_v2(sym)}` until `{until_str}`\n"
    else:
        msg += "*⏸️ Symbols on Pause:* `none`\n"

    # Глобальная пауза
    if is_trading_globally_paused():
        pause_until_str = global_trading_pause_until.strftime("%H:%M:%S") if global_trading_pause_until else "?"
        msg += f"*⛔ Global Pause Active:* until `{pause_until_str}`\n"
    else:
        msg += "*⛔ Global Pause:* `inactive`\n"

    send_telegram_message(msg, force=True, parse_mode="MarkdownV2")


@register_command("/growth", category="Статистика")
@handle_errors
def cmd_growth(message, state=None, stop_event=None):
    """
    📈 Рост капитала: старт → сейчас, ROI, цель
    """
    import os
    from datetime import datetime

    from telegram.telegram_utils import send_telegram_message
    from utils_core import get_cached_balance

    # Фиксированный путь к файлу сессии
    session_file = "data/session_growth.json"

    # Текущий баланс
    balance_now = get_cached_balance()

    # Загружаем/создаём стартовый
    if os.path.exists(session_file):
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        balance_start = data.get("start_balance", balance_now)
        start_time = datetime.fromisoformat(data.get("start_time", datetime.utcnow().isoformat()))
    else:
        balance_start = balance_now
        start_time = datetime.utcnow()
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump({"start_balance": balance_start, "start_time": start_time.isoformat()}, f)

    profit = balance_now - balance_start
    roi = (profit / balance_start) * 100 if balance_start else 0
    duration = datetime.utcnow() - start_time
    hours = int(duration.total_seconds() // 3600)
    days = duration.days

    # Milestone цель
    next_goal = int((balance_start + 25) // 25) * 25 + 25

    msg = (
        "*📈 Capital Growth*\n"
        f"• Start: `{balance_start:.2f}` USDC\n"
        f"• Now: `{balance_now:.2f}` USDC\n"
        f"• Net Profit: `{profit:.2f}` USDC\n"
        f"• ROI: `{roi:.2f}` %\n"
        f"• Running: `{days}d {hours%24}h`\n"
        f"• Next Milestone: `{next_goal} USDC`\n"
    )
    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)


@register_command("/failstats", category="Статистика")
@handle_errors
def cmd_failstats(message, state=None, stop_event=None):
    """
    📉 Символы с худшей статистикой (risk_factor)
    """
    import json

    from core.fail_stats_tracker import get_symbol_risk_factor

    try:
        path = "data/failure_log.json"
        if not os.path.exists(path):
            send_telegram_message("📭 failure_log.json not found.", force=True)
            return

        with open(path, encoding="utf-8") as f:
            log_data = json.load(f)

        stats = []
        for symbol, info in log_data.items():
            count = info.get("fail_count", 0)
            r, _ = get_symbol_risk_factor(symbol)
            stats.append((symbol, count, r))

        top = sorted(stats, key=lambda x: x[2])[:5]  # по наименьшему risk_factor
        if not top:
            send_telegram_message("✅ No symbols with low risk factor.", force=True)
            return

        msg = "*📉 Worst Symbols (by risk factor)*\n"
        for s, c, r in top:
            msg += f"• `{s}` → risk: `{r:.2f}`, fails: `{c}`\n"

        send_telegram_message(msg, parse_mode="MarkdownV2", force=True)

    except Exception as e:
        send_telegram_message(f"❌ /failstats error: {e}", force=True)


@register_command("/debugpanel", category="Статистика")
@handle_errors
def cmd_debugpanel(message, state=None, stop_event=None):
    """
    🧠 Полный статус: баланс, лимиты, риски, паузы, PnL
    """
    import datetime

    from core.risk_guard import symbol_last_entry
    from core.runtime_state import global_trading_pause_until, is_trading_globally_paused, paused_symbols
    from core.trade_engine import open_positions_count
    from tp_logger import get_today_pnl_from_csv
    from utils_core import get_cached_balance, get_runtime_config

    cfg = get_runtime_config()
    balance = get_cached_balance()
    now = datetime.datetime.utcnow()

    msg = "*🧠 Debug Panel*\n\n"
    msg += f"• 💰 Balance: `{balance:.2f}` USDC\n"
    msg += f"• ⚙️ Max Positions: `{cfg.get('max_concurrent_positions', '?')}`\n"
    msg += f"• 🎯 Risk Multiplier: `{cfg.get('risk_multiplier', '?')}`\n"
    msg += f"• 🧮 Hourly Trade Limit: `{cfg.get('max_hourly_trade_limit', '?')}`\n"
    msg += f"• ⏳ Cooldown: `{cfg.get('cooldown_minutes', '?')} min`\n"
    msg += f"• 🧩 SL %: `{cfg.get('SL_PERCENT', '?') * 100:.2f}%`\n"
    msg += f"• 🎯 TP Levels: `{cfg.get('step_tp_levels', [])}`\n"
    msg += f"• 📈 TP Sizes: `{cfg.get('step_tp_sizes', [])}`\n"
    msg += f"• 🕒 Max Hold: `{cfg.get('max_hold_minutes', '?')} min`\n"
    msg += f"• 🛑 Margin Cap: `{cfg.get('max_margin_percent', '?') * 100:.0f}%`\n"
    msg += f"• 🔄 Active Positions: `{open_positions_count}`\n"

    # Paused symbols
    paused = []
    for sym, until in paused_symbols.items():
        mins = int((until - now).total_seconds() // 60)
        paused.append(f"{sym} ({mins}m)")
    msg += f"• ⏸ Paused Symbols: `{', '.join(paused) if paused else 'none'}`\n"

    # Anti-reentry
    reentry = []
    for sym, ts in symbol_last_entry.items():
        age = int((now - ts).total_seconds())
        if age < 300:
            reentry.append(f"{sym} ({age}s ago)")
    msg += f"• 🚫 Anti-Reentry: `{', '.join(reentry) if reentry else 'none'}`\n"

    # Global pause
    if is_trading_globally_paused():
        until_str = global_trading_pause_until.strftime("%H:%M:%S") if global_trading_pause_until else "?"
        msg += f"• ⛔ Global Pause: `until {until_str}`\n"
    else:
        msg += "• ⛔ Global Pause: `inactive`\n"

    # Daily PnL
    try:
        pnl = get_today_pnl_from_csv()
        msg += f"• 📉 Daily PnL: `{pnl:.2f}` USDC\n"
    except Exception as e:
        msg += f"• 📉 Daily PnL: error ({e})\n"

    send_telegram_message(msg, parse_mode="MarkdownV2", force=True)


# === Основной хендлер ===


def handle_telegram_command(message, state, stop_event=None):
    """
    Главный обработчик Telegram-команд через COMMAND_REGISTRY
    """
    log(f"All registered commands: {list(COMMAND_REGISTRY.keys())}", level="DEBUG")
    msg_date = message.get("date", 0)
    session_start = state.get("session_start_time", 0)
    if msg_date and session_start and msg_date < session_start:
        return

    text = message.get("text", "").strip().lower()

    # 1) точное совпадение
    if text in COMMAND_REGISTRY:
        try:
            COMMAND_REGISTRY[text]["handler"](message, state, stop_event)
        except Exception as e:
            log(f"[Telegram] Error in {text}: {e}", level="ERROR")
            send_telegram_message(f"❌ Error: {e}", force=True)
        return

    # 2) возможно с аргументом (/open 5)
    base = text.split()[0]
    for cmd_text, cmd_info in COMMAND_REGISTRY.items():
        if base == cmd_text:
            try:
                cmd_info["handler"](message, state, stop_event)
            except Exception as e:
                log(f"[Telegram] Error in {base}: {e}", level="ERROR")
                send_telegram_message(f"❌ Error: {e}", force=True)
            return

    send_telegram_message("Command not recognized. Try /help", force=True)
