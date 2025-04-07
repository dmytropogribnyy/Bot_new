import os
import signal
import threading
import time
from datetime import datetime

from config import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    MIN_NOTIONAL,
    RISK_DRAWDOWN_THRESHOLD,
    SL_PERCENT,
    VERBOSE,
    exchange,
    is_aggressive,
    trade_stats,
    trade_stats_lock,
)
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
    calculate_position_size,
    calculate_risk_amount,
    enter_trade,
    get_position_size,
)
from ip_monitor import start_ip_monitor
from pair_selector import start_symbol_rotation
from telegram.telegram_commands import handle_stop, handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_adaptive_risk_percent, get_cached_balance, load_state, save_state
from utils_logging import log, log_dry_entry, notify_error, now

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def signal_handler(sig, frame):
    log("Force stopping bot due to Ctrl+C", important=True, level="INFO")
    os._exit(1)


signal.signal(signal.SIGINT, signal_handler)


def load_symbols():
    from pair_selector import select_active_symbols

    # Run select_active_symbols in a separate thread with a timeout
    result = []

    def run_select_active_symbols():
        try:
            symbols = select_active_symbols(exchange, last_trade_times, last_trade_times_lock)
            result.append(symbols)
        except Exception as e:
            log(f"Error in select_active_symbols: {e}", level="ERROR")
            result.append([])

    thread = threading.Thread(target=run_select_active_symbols)
    thread.daemon = True
    thread.start()

    # Manual timeout loop
    start_time = time.time()
    timeout = 30  # 30 seconds timeout
    while time.time() - start_time < timeout:
        if not thread.is_alive():
            break
        time.sleep(0.1)

    if thread.is_alive():
        log(f"Timeout in select_active_symbols after {timeout} seconds", level="ERROR")
        thread._stop()  # Attempt to stop the thread (not guaranteed to work)
        return []

    return result[0] if result else []


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
                            log(f"Current shutdown state: {state.get('shutdown')}", level="INFO")
                            send_telegram_message(
                                escape_markdown_v2("✅ All positions closed. Bot stopped."),
                                force=True,
                            )
                            if state.get("shutdown"):
                                log("Shutdown flag detected — exiting fully.", level="INFO")
                                os._exit(0)
                            break
                        else:
                            log(f"Waiting for {open_trades} open positions...", level="INFO")
                    time.sleep(10)
                    continue

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

                symbols = load_symbols()
                log(f"Checking {len(symbols)} symbols in trading loop", level="INFO")

                max_positions = 5
                open_positions = 0
                for symbol in symbols:
                    position_size = get_position_size(symbol)
                    if position_size != 0:
                        open_positions += 1

                active_symbols = []
                with last_trade_times_lock:
                    for symbol in symbols:
                        last_time = last_trade_times.get(symbol)
                        if last_time and (datetime.utcnow() - last_time).total_seconds() < 1800:
                            log(f"{symbol} ⏳ Skipped due to cooldown", level="INFO")
                            continue
                        active_symbols.append(symbol)

                for symbol in active_symbols:
                    if get_position_size(symbol) != 0:
                        continue
                    if open_positions >= max_positions:
                        log(
                            f"Max positions ({max_positions}) reached, skipping {symbol}",
                            level="INFO",
                        )
                        continue

                    df = fetch_data(symbol)
                    result = should_enter_trade(
                        symbol, df, exchange, last_trade_times, last_trade_times_lock
                    )
                    if isinstance(result, tuple) and result[0] in ["buy", "sell"]:
                        entry = df["close"].iloc[-1]
                        stop = (
                            entry * (1 - SL_PERCENT)
                            if result[0] == "buy"
                            else entry * (1 + SL_PERCENT)
                        )
                        risk_percent = get_adaptive_risk_percent(balance)
                        with trade_stats_lock:
                            if trade_stats["pnl"] < -RISK_DRAWDOWN_THRESHOLD:
                                risk_percent *= 0.5
                                log(f"⚠️ Risk lowered due to drawdown: {risk_percent * 100:.1f}%")
                            elif balance < trade_stats["initial_balance"] * 0.85:
                                risk_percent *= 0.6
                                log(
                                    f"⚠️ Risk lowered due to capital drop: {risk_percent * 100:.1f}%"
                                )
                        base_risk = risk_percent
                        score = result[1] if isinstance(result, tuple) else 0
                        if score == 3:
                            risk_percent *= 0.7
                            log(
                                f"⚠️ Entry score {score}/5 → reduced risk: base {base_risk * 100:.1f}% → effective {risk_percent * 100:.1f}%"
                            )
                        elif score >= 4:
                            log(f"📈 Entry score {score}/5 → full risk: {risk_percent * 100:.1f}%")
                        else:
                            log(
                                f"Entry score {score}/5 → using base risk: {risk_percent * 100:.1f}%"
                            )

                        risk = calculate_risk_amount(balance, risk_percent)
                        qty = calculate_position_size(entry, stop, risk)
                        if qty * entry >= MIN_NOTIONAL:
                            if DRY_RUN:
                                log(
                                    f"[DRY] Entering {result[0].upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})",
                                    level="INFO",
                                )
                                log_dry_entry(
                                    f"{result[0].upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})"
                                )
                                msg = f"DRY RUN: {result[0].upper()} {symbol} at {entry:.5f} (qty: {qty:.2f})"
                                send_telegram_message(msg, force=True)
                            else:
                                enter_trade(symbol, result[0], qty, score)
                                position_timestamps[symbol] = now()
                                log(
                                    f"Entered {result[0].upper()} on {symbol} at {entry:.5f} (qty: {qty:.2f})",
                                    level="INFO",
                                )
                save_state(state)
            except Exception as e:
                error_msg = f"Error in main loop: {str(e)}"
                notify_error(error_msg)
                log(error_msg, level="ERROR")
                with trade_stats_lock:
                    trade_stats["api_errors"] += 1
                    if trade_stats["api_errors"] >= 5:
                        send_telegram_message(
                            escape_markdown_v2("⚠️ 5+ API errors — pausing for 5 minutes"),
                            force=True,
                        )
                        log("Pausing for 5 minutes due to 5+ API errors", level="WARNING")
                        time.sleep(300)
                        trade_stats["api_errors"] = 0
            time.sleep(10)
    except KeyboardInterrupt:
        log("Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        msg = "🛑 Bot manually stopped via console (Ctrl+C)"
        send_telegram_message(msg, force=True)


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
        target=lambda: start_symbol_rotation(last_trade_times, last_trade_times_lock),
        daemon=True,
    ).start()
    start_trading_loop()
