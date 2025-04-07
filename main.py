import threading
import time

from config import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    VERBOSE,
    is_aggressive,
)
from core.engine_controller import run_trading_cycle
from ip_monitor import start_ip_monitor
from pair_selector import select_active_symbols, start_symbol_rotation
from telegram.telegram_commands import handle_stop, handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import load_state, save_state
from utils_logging import log


def load_symbols():
    return select_active_symbols()


def start_trading_loop():
    state = {**load_state(), "stopping": False, "shutdown": False}
    save_state(state)

    mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
    log(f"[Refactor] Starting bot in {mode} mode...", important=True, level="INFO")

    message = (
        f"Bot started in {mode} mode\n"
        f"Mode: {'SAFE' if not is_aggressive else 'AGGRESSIVE'}\n"
        f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    )
    send_telegram_message(escape_markdown_v2(message), force=True)

    symbols = load_symbols()
    log(f"[Refactor] Loaded symbols: {symbols}", important=True, level="INFO")

    try:
        while True:
            state = load_state()

            if state.get("pause") or state.get("stopping"):
                log("[Refactor] Paused or stopping...", level="INFO")
                time.sleep(10)
                continue

            run_trading_cycle(symbols)
            save_state(state)
            time.sleep(10)

    except KeyboardInterrupt:
        log("[Refactor] Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        send_telegram_message("🛑 Bot manually stopped via console (Ctrl+C)", force=True)


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

    start_trading_loop()
