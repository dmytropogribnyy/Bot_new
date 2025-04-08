import os
import threading
import time

import pandas as pd

from config import AGGRESSIVENESS_THRESHOLD, DRY_RUN
from core.aggressiveness_controller import get_aggressiveness_score
from core.balance_watcher import check_balance_change
from core.entry_logger import log_entry
from core.notifier import notify_dry_trade, notify_error
from core.symbol_processor import process_symbol
from core.trade_engine import (
    close_dry_trade,
    close_real_trade,
    enter_trade,
    get_position_size,
    last_trade_info,
)
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, load_state
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()
last_balance = 0
MIN_SCORE_DELTA_SWITCH = 2  # You can move this to config.py if needed


def get_smart_switch_stats():
    try:
        if not os.path.exists("data/tp_performance.csv"):
            log(
                "[SmartSwitch] tp_performance.csv not found, skipping winrate calculation.",
                level="WARNING",
            )
            return 0.5  # Возвращаем нейтральную winrate на старте

        df = pd.read_csv("data/tp_performance.csv", parse_dates=["Date"])
        recent = df[df["ResultType"] == "smart_switch"].tail(10)
        winrate = len(recent[recent["PnL (%)"] > 0]) / len(recent) if not recent.empty else 0
        return round(winrate, 2)
    except Exception as e:
        log(f"[SmartSwitch] Failed to calculate winrate: {e}", level="WARNING")
        return 0.5  # Возвращаем нейтральную winrate при ошибке


def get_adaptive_switch_limit(balance, active_positions, recent_switch_winrate):
    base_limit = 1 if balance < 50 else 2
    if active_positions == 0:
        base_limit += 1
    if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD:  # Используем порог из config
        base_limit += 1
    if recent_switch_winrate > 0.7:
        base_limit += 1
    elif recent_switch_winrate < 0.3:
        base_limit -= 1
    return max(1, min(base_limit, 5))


def run_trading_cycle(symbols):
    global last_balance
    state = load_state()

    if state.get("pause") or state.get("stopping"):
        if state.get("stopping"):
            open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
            if open_trades == 0:
                log("All positions closed — stopping bot.", level="INFO")
                send_telegram_message(
                    escape_markdown_v2("✅ All positions closed. Bot stopped."), force=True
                )
                if state.get("shutdown"):
                    log("Shutdown flag detected — exiting fully.", level="INFO")
                    os._exit(0)
                return
            else:
                log(f"Waiting for {open_trades} open positions...", level="INFO")
        time.sleep(10)
        return

    balance = get_cached_balance()
    last_balance = check_balance_change(balance, last_balance)
    log(f"Balance for cycle: {round(balance, 2)} USDC", level="DEBUG")

    active_positions = sum(get_position_size(sym) > 0 for sym in symbols)
    recent_wr = get_smart_switch_stats()
    switch_limit = get_adaptive_switch_limit(balance, active_positions, recent_wr)
    smart_switch_count = 0

    for symbol in symbols:
        try:
            log(f"🔍 Checking {symbol}", level="INFO")
            trade = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade:
                continue

            # 🧠 Smart Switching Check
            current_trade = last_trade_info.get(symbol)
            if current_trade:
                current_score = current_trade.get("score", 0)
                new_score = trade.get("score", 0)
                if new_score - current_score >= MIN_SCORE_DELTA_SWITCH:
                    if smart_switch_count >= switch_limit:
                        log(
                            f"⚠️ Smart Switch skipped for {symbol} — limit reached ({switch_limit})",
                            level="WARNING",
                        )
                        continue
                    log(
                        f"🧠 Smart Switch: Closing {symbol} (old score: {current_score}) → new score: {new_score}",
                        level="INFO",
                    )
                    switch_msg = (
                        f"🔄 *Smart Switch Activated*\n"
                        f"• `{symbol}` — old score: *{current_score}*, new: *{new_score}*\n"
                        f"• Action: closing old position and reopening"
                    )
                    send_telegram_message(escape_markdown_v2(switch_msg), force=True)
                    if DRY_RUN:
                        close_dry_trade(symbol)
                    else:
                        close_real_trade(symbol)
                    smart_switch_count += 1
                    time.sleep(1)
                else:
                    log(
                        f"Skipping {symbol}: current trade score {current_score} >= new {new_score}",
                        level="INFO",
                    )
                    continue

            # Execute trade
            if DRY_RUN:
                notify_dry_trade(trade)
                log_entry(trade, status="SUCCESS", mode="DRY_RUN")
            else:
                enter_trade(trade["symbol"], trade["direction"], trade["qty"], trade["score"])
                log_entry(trade, status="SUCCESS", mode="REAL_RUN")

        except Exception as e:
            notify_error(f"🔥 Error during {symbol}: {str(e)}")
