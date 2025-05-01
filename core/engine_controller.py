# core/engine_controller.py
# core/engine_controller.py

import os
import threading
import time

import pandas as pd

from common.config_loader import AGGRESSIVENESS_THRESHOLD, DRY_RUN  # ✅ Добавляем сюда
from core.aggressiveness_controller import get_aggressiveness_score
from core.entry_logger import log_entry
from core.notifier import notify_dry_trade, notify_error
from core.risk_utils import get_adaptive_risk_percent, get_max_positions
from telegram.telegram_utils import send_telegram_message
from utils_core import get_cached_balance, load_state, set_leverage_for_symbols
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()
last_balance = 0
MIN_SCORE_DELTA_SWITCH = 2
last_check_log_time = 0
last_balance_log_time = 0


def get_smart_switch_stats():
    try:
        if not os.path.exists("data/tp_performance.csv"):
            log(
                "[SmartSwitch] tp_performance.csv not found, skipping winrate calculation.",
                level="WARNING",
            )
            return 0.5

        df = pd.read_csv("data/tp_performance.csv", parse_dates=["Date"])
        recent = df[df["Result"] == "smart_switch"].tail(10)
        winrate = len(recent[recent["PnL (%)"] > 0]) / len(recent) if not recent.empty else 0
        return round(winrate, 2)
    except Exception as e:
        log(f"[SmartSwitch] Failed to calculate winrate: {e}", level="WARNING")
        return 0.5


def get_adaptive_switch_limit(balance, active_positions, recent_switch_winrate, aggressiveness_threshold):
    base_limit = 1 if balance < 50 else 2
    if active_positions == 0:
        base_limit += 1
    if get_aggressiveness_score() > aggressiveness_threshold:
        base_limit += 1
    if recent_switch_winrate > 0.7:
        base_limit += 1
    elif recent_switch_winrate < 0.3:
        base_limit -= 1
    return max(1, min(base_limit, 5))


def run_trading_cycle(symbols, stop_event):
    # Ленивые импорты, чтобы разорвать циклы
    from core.symbol_processor import process_symbol
    from core.trade_engine import (
        close_dry_trade,
        close_real_trade,
        enter_trade,
        get_position_size,
        trade_manager,
    )

    state = load_state()

    # Установка плеча
    set_leverage_for_symbols()

    # Адаптивный риск и позиции
    balance = get_cached_balance()
    get_adaptive_risk_percent(balance)
    get_max_positions(balance)

    # Обработка флага остановки
    if state.get("stopping"):
        open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
        log(f"Open trades count: {open_trades}", level="DEBUG")
        if open_trades == 0:
            log("All positions closed — stopping bot.", level="INFO")
            send_telegram_message("✅ All positions closed. Bot stopped.", force=True)
            if state.get("shutdown"):
                log("Shutdown flag detected — exiting fully.", level="INFO")
                os._exit(0)
        else:
            log(f"Waiting for {open_trades} open positions...", level="INFO")
        return

    # Основной торговый цикл
    balance = get_cached_balance()

    active_positions = sum(get_position_size(sym) > 0 for sym in symbols)
    recent_wr = get_smart_switch_stats()
    switch_limit = get_adaptive_switch_limit(balance, active_positions, recent_wr, AGGRESSIVENESS_THRESHOLD)
    smart_switch_count = 0

    for symbol in symbols:
        if stop_event.is_set():
            log(f"[Trading Cycle] Stop signal received, aborting cycle for {symbol}.", level="INFO")
            break

        try:
            log(f"🔍 Checking {symbol}", level="DEBUG")  # Просто лог на каждую проверку

            trade_data = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade_data:
                continue

            score = trade_data["score"]
            is_reentry = trade_data["is_reentry"]

            # Smart switch
            current_trade = trade_manager.get_trade(symbol)
            if current_trade:
                current_score = current_trade.get("score", 0)
                if score - current_score >= MIN_SCORE_DELTA_SWITCH:
                    if smart_switch_count < switch_limit:
                        log(
                            f"🧠 Smart Switch: {symbol} ({current_score}→{score})",
                            level="INFO",
                        )
                        send_telegram_message(
                            f"🔄 *Smart Switch* `{symbol}`: {current_score}→{score}",
                            force=True,
                            parse_mode="MarkdownV2",
                        )
                        if DRY_RUN:
                            close_dry_trade(symbol)
                        else:
                            close_real_trade(symbol)
                        smart_switch_count += 1
                        is_reentry = True
                        time.sleep(1)
                    else:
                        log(
                            f"⚠️ Smart Switch skipped for {symbol} — limit reached ({switch_limit})",
                            level="WARNING",
                        )
                        continue
                else:
                    continue

            # Вход в сделку
            if DRY_RUN:
                notify_dry_trade(trade_data)
                log_entry(trade_data, status="SUCCESS", mode="DRY_RUN")
            enter_trade(
                trade_data["symbol"],
                trade_data["direction"],
                trade_data["qty"],
                trade_data["score"],
                is_reentry,
            )
            if not DRY_RUN:
                log_entry(trade_data, status="SUCCESS", mode="REAL_RUN")

        except Exception as e:
            notify_error(f"🔥 Error during {symbol}: {str(e)}")
            log(f"Error in trading cycle for {symbol}: {e}", level="ERROR")
