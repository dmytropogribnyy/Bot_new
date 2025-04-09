import threading
import time

from config import (
    AGGRESSIVENESS_THRESHOLD,
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    VERBOSE,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.engine_controller import run_trading_cycle
from ip_monitor import start_ip_monitor
from pair_selector import select_active_symbols, start_symbol_rotation
from telegram.telegram_commands import handle_stop, handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import send_telegram_message
from utils_core import load_state, save_state
from utils_logging import log


def load_symbols():
    return select_active_symbols()


def start_trading_loop():
    state = {**load_state(), "stopping": False, "shutdown": False}
    save_state(state)

    mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
    log(f"[Refactor] Starting bot in {mode} mode...", important=True, level="INFO")

    aggressive_mode = get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD
    mode_text = "AGGRESSIVE" if aggressive_mode else "SAFE"

    message = (
        f"Bot started in {mode} mode\n"
        f"Mode: {mode_text}\n"
        f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    )
    send_telegram_message(message, force=True, parse_mode="")

    symbols = load_symbols()
    log(f"[Refactor] Loaded symbols: {symbols}", important=True, level="INFO")

    # Разбиваем пары на группы по 5
    group_size = 5
    symbol_groups = [symbols[i : i + group_size] for i in range(0, len(symbols), group_size)]
    current_group_index = 0

    try:
        while True:
            state = load_state()

            if state.get("pause") or state.get("stopping"):
                log("[Refactor] Paused or stopping...", level="INFO")
                time.sleep(10)
                continue

            # Проверяем текущую группу
            current_group = symbol_groups[current_group_index]
            log(
                f"Checking group {current_group_index + 1}/{len(symbol_groups)}: {current_group}",
                level="DEBUG",
            )
            run_trading_cycle(current_group)

            # Переходим к следующей группе
            current_group_index = (current_group_index + 1) % len(symbol_groups)

            save_state(state)
            time.sleep(10)
    except KeyboardInterrupt:
        log("[Refactor] Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        send_telegram_message(
            "🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode=""
        )


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
