# main.py
import os
import threading
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from common.config_loader import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    MAX_POSITIONS,
    RUNNING,
    USE_TESTNET,
    VERBOSE,
    initialize_risk_percent,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.engine_controller import run_trading_cycle
from core.exchange_init import exchange
from core.trade_engine import close_real_trade, trade_manager
from htf_optimizer import analyze_htf_winrate
from ip_monitor import start_ip_monitor
from pair_selector import select_active_symbols, start_symbol_rotation
from score_heatmap import generate_score_heatmap
from stats import (
    generate_daily_report,
    send_halfyear_report,
    send_monthly_report,
    send_quarterly_report,
    send_weekly_report,
    send_yearly_report,
    should_run_optimizer,
)
from telegram.telegram_commands import _initiate_stop, handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import send_daily_summary, send_telegram_message
from tp_optimizer import run_tp_optimizer
from tp_optimizer_ml import analyze_and_optimize_tp
from utils_core import initialize_cache, load_state, save_state
from utils_logging import log

# Initialize RISK_PERCENT after imports to avoid circular import issues
initialize_risk_percent()

stop_event = threading.Event()


# Rest of the file remains unchanged
def load_symbols():
    symbols = select_active_symbols()
    if not symbols:
        log("No active symbols loaded, stopping bot", level="ERROR")
        send_telegram_message("⚠️ No active symbols loaded, stopping bot", force=True)
        stop_event.set()
        return []
    return symbols


def start_trading_loop():
    initialize_cache()

    positions = exchange.fetch_positions()
    active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
    if active_positions > MAX_POSITIONS:
        log(
            f"[Startup] Found {active_positions} positions, but MAX_POSITIONS is {MAX_POSITIONS}. Closing excess positions...",
            level="INFO",
        )
        for pos in positions:
            if float(pos.get("contracts", 0)) != 0:
                symbol = pos["symbol"]
                close_real_trade(symbol)
                active_positions -= 1
                if active_positions <= MAX_POSITIONS:
                    break

    state = load_state()
    state["stopping"] = False
    state["shutdown"] = False
    save_state(state)

    mode = "TESTNET" if USE_TESTNET else "REAL_RUN"
    if DRY_RUN:
        mode += " (DRY_RUN)"
    log(f"[Refactor] Starting bot in {mode} mode...", important=True, level="INFO")

    score = round(get_aggressiveness_score(), 2)
    if score >= 0.75:
        bias = "🔥 HIGH"
    elif score >= 0.5:
        bias = "⚡ MODERATE"
    else:
        bias = "🧊 LOW"

    message = f"Bot started in {mode} mode\n" f"Strategy Bias: {bias} ({score})\n" f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    send_telegram_message(message, force=True, parse_mode="")

    symbols = load_symbols()
    log(f"[Refactor] Loaded symbols: {symbols}", important=True, level="INFO")
    if not symbols:
        return  # Exit if no symbols loaded

    group_size = 5
    symbol_groups = [symbols[i : i + group_size] for i in range(0, len(symbols), group_size)]
    current_group_index = 0

    try:
        while RUNNING and not stop_event.is_set():
            state = load_state()

            if state.get("stopping") or state.get("shutdown"):
                # Use get_open_positions() to check actual exchange state
                from core.binance_api import get_open_positions

                open_positions = get_open_positions()
                if not open_positions:
                    msg = "[Main] Bot is stopping. No open trades. "
                    if state.get("shutdown"):
                        msg += "Shutting down..."
                        log(msg, level="INFO", important=True)
                        send_telegram_message("✅ Shutdown complete. No open trades. Exiting...", force=True)
                        state["stopping"] = False
                        state["shutdown"] = False
                        save_state(state)
                        os._exit(0)
                    else:
                        msg += "Will stop shortly..."
                        log(msg, level="INFO")
                        time.sleep(30)
                        continue
                else:
                    # Format positions for better visibility
                    symbols = [pos["symbol"] for pos in open_positions]
                    symbols_str = ", ".join(symbols)
                    msg = f"⏳ Still open positions ({len(open_positions)}): {symbols_str}. Waiting..."
                    log(msg, level="INFO")
                    send_telegram_message(msg, force=True)

                    # Actively try to close positions
                    for pos in open_positions:
                        symbol = pos["symbol"]
                        log(f"[Stop] Closing position for {symbol}", level="INFO")
                        close_real_trade(symbol)
                        time.sleep(1)

                    time.sleep(10)
                    continue

            try:
                positions = exchange.fetch_positions()
                active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
                if active_positions >= MAX_POSITIONS:
                    log(
                        f"[Main] Max open positions ({MAX_POSITIONS}) reached. Active: {active_positions}. Skipping cycle...",
                        level="INFO",
                    )
                    time.sleep(30)
                    continue
                if active_positions > 0 and not trade_manager._trades:
                    log(
                        f"[Main] State mismatch: {active_positions} positions on exchange, but trade_manager empty. Forcing sync...",
                        level="WARNING",
                    )
                    for pos in positions:
                        if float(pos.get("contracts", 0)) != 0:
                            close_real_trade(pos["symbol"])
                    continue
            except Exception as e:
                log(f"[Main] Failed to fetch positions: {e}", level="ERROR")
                time.sleep(10)
                continue

            current_group = symbol_groups[current_group_index]
            state = load_state()
            if state.get("stopping") or stop_event.is_set():
                log("[Main] Stopping detected before trading cycle...", level="INFO")
                time.sleep(10)
                continue

            run_trading_cycle(current_group, stop_event)
            current_group_index = (current_group_index + 1) % len(symbol_groups)
            time.sleep(10)

        if not stop_event.is_set():
            log(
                "[Main] RUNNING = False detected. Graceful shutdown triggered.",
                important=True,
                level="INFO",
            )
            send_telegram_message("🛑 Bot stopped via graceful shutdown.", force=True, parse_mode="")

    except KeyboardInterrupt:
        log("[Main] Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        send_telegram_message("🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode="")
        stop_event.set()


def start_report_loops():
    def daily_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.hour == 21 and t.minute == 0:
                generate_daily_report()
                time.sleep(60)
            time.sleep(10)

    def weekly_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                send_weekly_report()
                time.sleep(60)
            time.sleep(10)

    def extended_reports_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.day == 1 and t.hour == 21 and t.minute == 0:
                send_monthly_report()
            if t.day == 1 and t.month in [1, 4, 7, 10] and t.hour == 21 and t.minute == 5:
                send_quarterly_report()
            if t.day == 1 and t.month in [1, 7] and t.hour == 21 and t.minute == 10:
                send_halfyear_report()
            if t.day == 1 and t.month == 1 and t.hour == 21 and t.minute == 15:
                send_yearly_report()
            time.sleep(10)

    def optimizer_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                    analyze_and_optimize_tp()
                else:
                    send_telegram_message(
                        "Not enough recent trades to optimize (min: 20)",
                        force=True,
                    )
                time.sleep(60)
            time.sleep(10)

    def heatmap_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.weekday() == 4 and t.hour == 20 and t.minute == 0:
                generate_score_heatmap(days=7)
                time.sleep(60)
            time.sleep(10)

    def htf_optimizer_loop():
        while not stop_event.is_set():
            t = datetime.now()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                analyze_htf_winrate()
                time.sleep(60)
            time.sleep(10)

    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=extended_reports_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()
    threading.Thread(target=heatmap_loop, daemon=True).start()
    threading.Thread(target=htf_optimizer_loop, daemon=True).start()


if __name__ == "__main__":
    import time

    from utils_core import reset_state_flags  # Add this import
    from utils_logging import add_log_separator, log

    # Add visual separator in log before starting
    add_log_separator()

    # Reset state flags at startup to ensure clean state
    reset_state_flags()
    log("State flags reset at startup", level="INFO")

    # Create and save session start time
    state = load_state()
    current_time = time.time()
    state["session_start_time"] = current_time
    save_state(state)
    log(f"New bot session started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}", level="INFO")

    from tp_logger import ensure_log_exists

    ensure_log_exists()

    threading.Thread(
        target=lambda: process_telegram_commands(state, handle_telegram_command),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: start_ip_monitor(_initiate_stop, interval_seconds=IP_MONITOR_INTERVAL_SECONDS),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: start_symbol_rotation(stop_event),
        daemon=True,
    ).start()
    threading.Thread(
        target=start_report_loops,
        daemon=True,
    ).start()

    # Start APScheduler for periodic tasks
    scheduler = BackgroundScheduler()
    # Ежедневный отчёт о сделках в 23:59
    scheduler.add_job(send_daily_summary, "cron", hour=23, minute=59)
    # Ротация торговых пар каждые 4 часа
    scheduler.add_job(select_active_symbols, "interval", hours=4)
    # Авто-оптимизация TP/SL каждое воскресенье в 10:00
    scheduler.add_job(analyze_and_optimize_tp, "cron", day_of_week="sun", hour=10)
    scheduler.start()
    log("Scheduler started with daily summary, pair rotation, and TP/SL optimizer", level="INFO")

    # Add proper shutdown handling
    try:
        start_trading_loop()
    finally:
        if scheduler.running:
            scheduler.shutdown()
            log("Scheduler shutdown completed", level="INFO")
