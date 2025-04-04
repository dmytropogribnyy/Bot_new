import time
import os
from datetime import datetime
from config import (
    exchange,
    ADAPTIVE_RISK_PERCENT,
    MIN_NOTIONAL,
    SL_PERCENT,
    trade_stats,
    trade_stats_lock,
    DRY_RUN,
    is_aggressive,
    MAX_HOLD_MINUTES,
    TIMEZONE,
    EXPORT_PATH,
    FIXED_PAIRS,
    VERBOSE,
)
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
    enter_trade,
    calculate_risk_amount,
    calculate_position_size,
    get_position_size,
)
from telegram.telegram_handler import send_telegram_message
from utils import (
    log,
    notify_error,
    log_dry_entry,
    now,
    load_state,
    save_state,
    get_cached_balance,
    get_cached_positions,
)
from telegram.telegram_utils import escape_markdown_v2
from tp_logger import log_trade_result

SYMBOLS_FILE = "data/dynamic_symbols.json"


def load_symbols():
    from pair_selector import select_active_symbols

    return select_active_symbols()


def start_trading_loop():
    state = {**load_state(), "stopping": False, "shutdown": False}
    save_state(state)

    mode = "DRY_RUN" if DRY_RUN else "REAL_RUN"
    log(f"Starting bot in {mode} mode...", important=True, level="INFO")

    message = (
        f"Bot started in {mode} mode\n"
        f"Mode: {'SAFE' if not is_aggressive else 'AGGRESSIVE'}\n"
        f"DRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    )
    send_telegram_message(escape_markdown_v2(message), force=True)
    log("Telegram start message sent (or attempted)", important=True, level="INFO")

    symbols = load_symbols()
    log(f"Loaded symbols: {symbols}", important=True, level="INFO")

    last_balance = 0
    position_timestamps = {}
    last_loop_log_time = time.time()

    if DRY_RUN:
        test_symbol = "BTC/USDC"
        enter_trade(test_symbol, "buy", 1.0, score=5)
        log(f"Test DRY BUY executed for {test_symbol}", level="INFO")

    try:
        while True:
            state = load_state()
            try:
                balance = get_cached_balance()
                with trade_stats_lock:
                    if last_balance == 0:
                        trade_stats["initial_balance"] = balance
                        log(f"Initial balance set: {balance} USDC", level="INFO")
                    elif balance > last_balance + 0.5:
                        delta = round(balance - last_balance, 2)
                        trade_stats["deposits_today"] += delta
                        trade_stats["deposits_week"] += delta
                        send_telegram_message(f"Deposit detected: +{delta} USDC")
                        log(f"Deposit detected: +{delta} USDC", level="INFO")
                    elif balance < last_balance - 0.5:
                        delta = round(last_balance - balance, 2)
                        trade_stats["withdrawals"] += delta
                        send_telegram_message(f"Withdrawal detected: -{delta} USDC")
                        log(f"Withdrawal detected: -{delta} USDC", level="INFO")
                last_balance = balance

                if state.get("pause") or state.get("stopping"):
                    if state.get("stopping"):
                        open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
                        if DRY_RUN:
                            log(
                                f"[DRY_RUN] Checking stop condition — open trades: {open_trades}",
                                level="INFO",
                            )
                        if open_trades == 0:
                            log("All positions closed — stopping bot.", level="INFO")
                            log(
                                f"Current shutdown state: {state.get('shutdown')}",
                                level="INFO",
                            )
                            send_telegram_message(
                                escape_markdown_v2(
                                    "✅ All positions closed. Bot stopped."
                                ),
                                force=True,
                            )
                            if state.get("shutdown"):
                                log(
                                    "Shutdown flag detected — exiting fully.",
                                    level="INFO",
                                )
                                os._exit(0)
                            break
                        else:
                            log(
                                f"Waiting for {open_trades} open positions...",
                                level="INFO",
                            )

                if state.get("shutdown"):
                    open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
                    if open_trades == 0:
                        log("No open positions — exiting fully.", level="INFO")
                        send_telegram_message(
                            escape_markdown_v2("✅ Bot stopped (shutdown)."),
                            force=True,
                        )
                        os._exit(0)
                    time.sleep(10)
                    continue

                now_time = time.time()
                if DRY_RUN or (now_time - last_loop_log_time > 600):
                    log("Starting symbol loop...", level="INFO")
                    last_loop_log_time = now_time

                for symbol in symbols:
                    if get_position_size(symbol) > 0:
                        continue
                    df = fetch_data(symbol)
                    result = should_enter_trade(symbol, df)
                    if result in ["buy", "sell"]:
                        entry = df["close"].iloc[-1]
                        stop = (
                            entry * (1 - SL_PERCENT)
                            if result == "buy"
                            else entry * (1 + SL_PERCENT)
                        )
                        risk = calculate_risk_amount(balance, ADAPTIVE_RISK_PERCENT)
                        qty = calculate_position_size(entry, stop, risk)
                        if qty * entry >= MIN_NOTIONAL:
                            if DRY_RUN:
                                log(
                                    f"[DRY] Entering {result.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})",
                                    level="INFO",
                                )
                                log_dry_entry(
                                    f"{result.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})"
                                )
                                msg = f"DRY RUN: {result.upper()} {symbol} at {entry:.5f} (qty: {qty:.2f})"
                                send_telegram_message(msg, force=True)
                            else:
                                enter_trade(symbol, result, qty)
                                position_timestamps[symbol] = now()
                                log(
                                    f"Entered {result.upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})",
                                    level="INFO",
                                )
                save_state(state)
            except Exception as e:
                error_msg = f"Error in main loop: {str(e)}"
                notify_error(error_msg)
                log(error_msg, level="ERROR")
                with trade_stats_lock:
                    trade_stats["api_errors"] += 1
            time.sleep(10)
    except KeyboardInterrupt:
        log("Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        msg = "🛑 Bot manually stopped via console (Ctrl+C)"
        send_telegram_message(msg, force=True)


if __name__ == "__main__":
    from telegram.telegram_handler import process_telegram_commands
    from telegram.telegram_commands import handle_telegram_command, handle_stop
    from ip_monitor import start_ip_monitor
    from config import IP_MONITOR_INTERVAL_SECONDS
    import threading

    state = load_state()
    threading.Thread(
        target=lambda: process_telegram_commands(state, handle_telegram_command),
        daemon=True,
    ).start()
    threading.Thread(
        target=lambda: start_ip_monitor(
            handle_stop, interval_seconds=IP_MONITOR_INTERVAL_SECONDS
        ),
        daemon=True,
    ).start()
    start_trading_loop()
