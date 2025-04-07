import os
import threading
import time

from config import DRY_RUN
from core.balance_watcher import check_balance_change
from core.entry_logger import log_entry
from core.notifier import notify_dry_trade, notify_error
from core.symbol_processor import process_symbol
from core.trade_engine import enter_trade, get_position_size
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance, load_state
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()
last_balance = 0


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

    for symbol in symbols:
        try:
            log(f"🔍 Checking {symbol}", level="INFO")
            trade = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade:
                continue

            if DRY_RUN:
                notify_dry_trade(trade)
                log_entry(trade, status="SUCCESS", mode="DRY_RUN")
            else:
                enter_trade(trade["symbol"], trade["direction"], trade["qty"], trade["score"])
                log_entry(trade, status="SUCCESS", mode="REAL_RUN")

        except Exception as e:
            notify_error(f"🔥 Error during {symbol}: {str(e)}")
