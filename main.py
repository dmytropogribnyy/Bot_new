import threading
import time
from datetime import datetime

from config import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    VERBOSE,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.engine_controller import run_trading_cycle
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
from telegram.telegram_commands import handle_stop, handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from tp_optimizer import run_tp_optimizer
from tp_optimizer_ml import analyze_and_optimize_tp
from utils_core import load_state, save_state
from utils_logging import log


def load_symbols():
    return select_active_symbols()


def start_trading_loop():
    # ✅ Всегда сбрасываем флаги при старте ран
    state = load_state()
    state["stopping"] = False
    state["shutdown"] = False
    save_state(state)

    mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
    log(f"[Refactor] Starting bot in {mode} mode...", important=True, level="INFO")

    # 🎯 Отображаем стратегическое смещение на основе score
    score = round(get_aggressiveness_score(), 2)
    if score >= 0.75:
        bias = "🔥 HIGH"
    elif score >= 0.5:
        bias = "⚡ MODERATE"
    else:
        bias = "🧊 LOW"

    message = (
        f"Bot started in {mode} mode\n"
        f"Strategy Bias: {bias} ({score})\n"
        f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    )
    send_telegram_message(message, force=True, parse_mode="")

    symbols = load_symbols()
    log(f"[Refactor] Loaded symbols: {symbols}", important=True, level="INFO")

    group_size = 5
    symbol_groups = [symbols[i : i + group_size] for i in range(0, len(symbols), group_size)]
    current_group_index = 0

    try:
        while True:
            state = load_state()

            # 🛑 Shutdown
            if state.get("shutdown"):
                open_trades = state.get("open_trades", [])
                if not open_trades:
                    log(
                        "[Main] Shutdown complete. No open trades. Exiting...",
                        level="INFO",
                        important=True,
                    )
                    send_telegram_message(
                        "✅ Shutdown complete. No open trades. Exiting...", force=True
                    )
                    break

            # 🟡 Stop
            if state.get("stopping"):
                open_trades = state.get("open_trades", [])

                if DRY_RUN:
                    from core.trade_engine import trade_manager

                    open_trades = list(trade_manager._trades.values())

                if not open_trades:
                    msg = "[Main] Bot is stopping. No open trades. "
                    msg += (
                        "Awaiting shutdown..." if state.get("shutdown") else "Will stop shortly..."
                    )
                else:
                    symbols = [t["symbol"] for t in open_trades]
                    msg = f"[Main] Bot is stopping. Waiting for trades to close: {symbols}"

                log(msg, level="INFO")
                time.sleep(30)
                continue

            current_group = symbol_groups[current_group_index]

            state = load_state()
            if state.get("stopping"):
                log("[Main] Stopping detected before trading cycle...", level="INFO")
                time.sleep(10)
                continue

            run_trading_cycle(current_group)
            current_group_index = (current_group_index + 1) % len(symbol_groups)
            time.sleep(10)

    except KeyboardInterrupt:
        log("[Main] Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        send_telegram_message(
            "🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode=""
        )


def start_report_loops():
    def daily_loop():
        while True:
            t = datetime.now()
            if t.hour == 21 and t.minute == 0:
                generate_daily_report()
                time.sleep(60)
            time.sleep(10)

    def weekly_loop():
        while True:
            t = datetime.now()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                send_weekly_report()
                time.sleep(60)
            time.sleep(10)

    def extended_reports_loop():
        while True:
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
        while True:
            t = datetime.now()
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                    analyze_and_optimize_tp()
                else:
                    send_telegram_message(
                        escape_markdown_v2("Not enough recent trades to optimize (min: 20)"),
                        force=True,
                    )
                time.sleep(60)
            time.sleep(10)

    def heatmap_loop():
        while True:
            t = datetime.now()
            if t.weekday() == 4 and t.hour == 20 and t.minute == 0:
                generate_score_heatmap(days=7)
                time.sleep(60)
            time.sleep(10)

    def htf_optimizer_loop():
        while True:
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
    state = load_state()
    threading.Thread(
        target=lambda: process_telegram_commands(state, handle_telegram_command),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: start_ip_monitor(handle_stop, interval_seconds=IP_MONITOR_INTERVAL_SECONDS),
        daemon=True,
    ).start()
    threading.Thread(
        target=start_symbol_rotation,
        daemon=True,
    ).start()
    threading.Thread(
        target=start_report_loops,
        daemon=True,
    ).start()

    start_trading_loop()
