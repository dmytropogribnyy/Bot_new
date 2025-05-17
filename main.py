# main.py
"""
Main trading loop for BinanceBot
Manages the core trading cycle, risk management, and drawdown protection
"""

import os
import threading
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

import telegram.telegram_commands as telegram_commands
from common.config_loader import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    MAX_POSITIONS,
    RUNNING,
    USE_TESTNET,
    VERBOSE,
    initialize_risk_percent,
    set_bot_status,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.exchange_init import exchange
from core.fail_stats_tracker import schedule_failure_decay
from core.failure_logger import log_failure
from core.risk_utils import check_drawdown_protection
from core.signal_feedback_loop import adjust_score_relax_boost, analyze_tp2_winrate, initialize_runtime_adaptive_config
from core.strategy import last_trade_times, last_trade_times_lock, should_enter_trade
from core.trade_engine import close_real_trade, enter_trade, trade_manager
from htf_optimizer import analyze_htf_winrate
from ip_monitor import start_ip_monitor
from missed_tracker import flush_best_missed_opportunities
from pair_selector import auto_cleanup_signal_failures, select_active_symbols, start_symbol_rotation, track_missed_opportunities
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
from symbol_activity_tracker import auto_adjust_relax_factors_from_missed
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import send_daily_summary, send_telegram_message
from tools.continuous_scanner import continuous_scan
from tp_logger import ensure_log_exists
from tp_optimizer import run_tp_optimizer
from tp_optimizer_ml import analyze_and_optimize_tp
from utils_core import get_cached_balance, initialize_cache, load_state, reset_state_flags, save_state
from utils_logging import add_log_separator, log

# Initialize RISK_PERCENT after imports to avoid circular import issues
initialize_risk_percent()

# Глобальное событие для остановки
stop_event = threading.Event()


def get_trading_signal(symbol):
    """
    Generate a trading signal based on candle analysis

    Args:
        symbol (str): Trading pair symbol

    Returns:
        dict: Signal data with side, qty, and score, or None if no signal
    """
    try:
        # Use the proper data fetching function that calculates indicators
        from core.strategy import fetch_data

        # Fetch data with all indicators calculated
        df = fetch_data(symbol)
        if df is None or len(df) < 10:
            log(f"[Signal] Insufficient data for {symbol}", level="WARNING")
            log_failure(symbol, ["insufficient_data"])
            return None

        # Process both buy and sell directions separately to preserve original logic
        buy_signal, buy_failures = should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock)
        sell_signal, sell_failures = should_enter_trade(symbol, df, exchange, last_trade_times, last_trade_times_lock)

        # If neither direction is valid, log combined failures
        if buy_signal is None and sell_signal is None:
            all_failures = list(set(buy_failures + sell_failures))
            log_failure(symbol, all_failures)
            return None

        # Determine the best direction based on score comparison (preserving original logic)
        if buy_signal and sell_signal:
            buy_direction, buy_score, buy_reentry = buy_signal
            sell_direction, sell_score, sell_reentry = sell_signal

            if buy_score > sell_score:
                direction, score, is_reentry = buy_signal
            else:
                direction, score, is_reentry = sell_signal
        elif buy_signal:
            direction, score, is_reentry = buy_signal
        elif sell_signal:
            direction, score, is_reentry = sell_signal
        else:
            return None

        # Calculate position size
        balance = get_cached_balance()
        from common.config_loader import get_adaptive_risk_percent
        from core.trade_engine import calculate_position_size

        risk_percent = get_adaptive_risk_percent(balance)
        risk_amount = balance * risk_percent
        entry_price = df["close"].iloc[-1]
        stop_price = entry_price * (1 - 0.007) if direction == "buy" else entry_price * (1 + 0.007)
        qty = calculate_position_size(entry_price, stop_price, risk_amount)

        return {"side": direction, "qty": qty, "score": score}
    except Exception as e:
        log(f"[Signal] Error generating signal for {symbol}: {e}", level="ERROR")
        log_failure(symbol, ["exception", str(e)])
        return None


def load_symbols():
    """
    Load active symbols for trading
    """
    symbols = select_active_symbols()
    if not symbols:
        log("No active symbols loaded, stopping bot", level="ERROR")
        send_telegram_message("⚠️ No active symbols loaded, stopping bot", force=True)
        stop_event.set()
        return []
    return symbols


def start_report_loops():
    """
    Start background loops for generating reports and optimizations
    """

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
                    send_telegram_message("Not enough recent trades to optimize (min: 20)", force=True)
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


def start_trading_loop():
    """
    Main trading loop for BinanceBot
    """
    log("Starting BinanceBot main trading loop", level="INFO")

    # Инициализация состояния бота
    set_bot_status("running")
    initialize_cache()

    # Получаем и выводим значение баланса при старте
    starting_balance = get_cached_balance()
    log(f"[Startup] Starting balance: {starting_balance:.2f} USDC", level="INFO", important=True)

    # Проверка позиций при старте
    positions = exchange.fetch_positions()
    active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
    if active_positions > MAX_POSITIONS:
        log(f"[Startup] Found {active_positions} positions, but MAX_POSITIONS is {MAX_POSITIONS}. Closing excess positions...", level="INFO")
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

    # Обновленное сообщение с информацией о балансе
    message = f"Bot started in {mode} mode\nBalance: {starting_balance:.2f} USDC\nStrategy Bias: {bias} ({score})\nDRY_RUN: {str(DRY_RUN)}, VERBOSE: {str(VERBOSE)}"
    send_telegram_message(message, force=True, parse_mode="")

    # Загрузка символов
    symbols = load_symbols()
    if symbols:
        symbols_str = ", ".join(symbols)
        log(f"[Refactor] Loaded {len(symbols)} active symbols: {symbols_str}", important=True, level="INFO")
    else:
        log("[Refactor] No active symbols loaded, exiting bot.", important=True, level="ERROR")
        return  # Exit if no symbols loaded

    # Группировка символов
    group_size = 5
    symbol_groups = [symbols[i : i + group_size] for i in range(0, len(symbols), group_size)]
    current_group_index = 0

    last_drawdown_check = 0
    trades_executed = 0

    try:
        while RUNNING and not stop_event.is_set():
            state = load_state()

            if state.get("stopping") or state.get("shutdown"):
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
                    symbols = [pos["symbol"] for pos in open_positions]
                    symbols_str = ", ".join(symbols)
                    msg = f"⏳ Still open positions ({len(open_positions)}): {symbols_str}. Waiting..."
                    log(msg, level="INFO")
                    send_telegram_message(msg, force=True)

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
                    log(f"[Main] Max open positions ({MAX_POSITIONS}) reached. Active: {active_positions}. Skipping cycle...", level="INFO")
                    time.sleep(30)
                    continue
                if active_positions > 0 and not trade_manager._trades:
                    log(f"[Main] State mismatch: {active_positions} positions on exchange, but trade_manager empty. Forcing sync...", level="WARNING")
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

            # Проверка просадки
            balance = get_cached_balance()
            if not balance:
                log("Failed to fetch balance. Retrying in 30 seconds.", level="ERROR")
                time.sleep(30)
                continue

            current_time = time.time()
            if current_time - last_drawdown_check >= 60 or trades_executed > 0:
                drawdown_status = check_drawdown_protection(balance)
                last_drawdown_check = current_time

                if drawdown_status["status"] == "paused":
                    log("Bot paused due to critical drawdown. Manual intervention required.", level="ERROR")
                    continue
                elif drawdown_status["status"] == "reduced_risk":
                    log(f"Risk reduced due to drawdown: {drawdown_status['drawdown']:.2f}%", level="WARNING")
                trades_executed = 0  # Сбрасываем счётчик после проверки

            # Проверка сигналов для текущей группы символов
            for symbol in current_group:
                try:
                    signal = get_trading_signal(symbol)
                    if signal:
                        side = signal["side"]
                        qty = signal["qty"]
                        score = signal.get("score", 5)

                        log(f"Received trading signal for {symbol}: {side} with qty {qty}, score {score}", level="INFO")
                        enter_trade(symbol, side, qty, score=score)
                        trades_executed += 1
                except Exception as e:
                    log(f"Error processing symbol {symbol}: {e}", level="ERROR")
                    continue

            # Переход к следующей группе
            current_group_index = (current_group_index + 1) % len(symbol_groups)
            time.sleep(10)

        if not stop_event.is_set():
            log("[Main] RUNNING = False detected. Graceful shutdown triggered.", important=True, level="INFO")
            send_telegram_message("🛑 Bot stopped via graceful shutdown.", force=True, parse_mode="")

    except KeyboardInterrupt:
        log("[Main] Bot manually stopped via console (Ctrl+C)", important=True, level="INFO")
        send_telegram_message("🛑 Bot manually stopped via console (Ctrl+C)", force=True, parse_mode="")
        stop_event.set()


if __name__ == "__main__":
    # Инициализация
    add_log_separator()
    reset_state_flags()
    log("State flags reset at startup", level="INFO")

    auto_cleanup_signal_failures()

    initialize_runtime_adaptive_config()
    log("✅ Adaptive config initialized based on current balance", level="INFO")

    from utils_core import get_runtime_config

    log(f"Runtime config at startup: {get_runtime_config()}", level="DEBUG")

    # Add TP2 winrate analysis at startup
    analyze_tp2_winrate()
    log("✅ TP2 winrate analysis initialized", level="INFO")

    state = load_state()
    current_time = time.time()
    state["session_start_time"] = current_time
    save_state(state)
    log(f"New bot session started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}", level="INFO")

    ensure_log_exists()

    # Phase 1: Run initial failure decay on startup
    schedule_failure_decay()  # Run initial decay on startup
    log("✅ Initial failure decay completed", level="INFO")

    # Phase 1: Verify configuration matches optimization requirements
    config = get_runtime_config()
    log(f"ATR threshold: {config.get('atr_threshold_percent')}, Volume threshold: {config.get('volume_threshold_usdc')}", level="DEBUG")
    if config.get("atr_threshold_percent", 0) > 6.0:
        log("⚠️ Warning: ATR threshold not optimized for scalping", level="WARNING")
    if config.get("volume_threshold_usdc", 0) > 5000:
        log("⚠️ Warning: Volume threshold not optimized for small accounts", level="WARNING")

    # ✅ Инициализируем scheduler заранее
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()

    # ✅ Установка времени запуска для ip_monitor логики
    import ip_monitor

    ip_monitor.boot_time = time.time()

    # Запуск фоновых задач
    threading.Thread(
        target=lambda: process_telegram_commands(state, lambda message: telegram_commands.handle_telegram_command(message, state, stop_event=stop_event)),
        daemon=True,
    ).start()

    threading.Thread(
        target=lambda: start_ip_monitor(
            lambda: telegram_commands._initiate_stop("ip_changed", stop_event=stop_event),
            interval_seconds=IP_MONITOR_INTERVAL_SECONDS,
        ),
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

    from core.status_logger import log_symbol_activity_status

    scheduler.add_job(send_daily_summary, "cron", hour=23, minute=59)
    scheduler.add_job(analyze_and_optimize_tp, "cron", day_of_week="sun", hour=10)
    scheduler.add_job(track_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(flush_best_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(auto_adjust_relax_factors_from_missed, "interval", minutes=30)
    scheduler.add_job(analyze_tp2_winrate, "interval", hours=24, id="tp2_risk_feedback")
    scheduler.add_job(schedule_failure_decay, "interval", hours=1, id="failure_decay")
    scheduler.add_job(continuous_scan, "interval", hours=2, id="inactive_scanner")
    scheduler.add_job(adjust_score_relax_boost, "interval", hours=1, id="score_relax_adjustment")
    scheduler.add_job(log_symbol_activity_status, "interval", minutes=10, id="status_logger")

    scheduler.start()
    log("Scheduler started with daily summary, pair rotation, TP/SL optimizer, missed opportunities tracking, TP2 risk feedback, failure decay, and score relax adjustment", level="INFO")

    try:
        start_trading_loop()
    finally:
        if scheduler.running:
            scheduler.shutdown()
            log("Scheduler shutdown completed", level="INFO")
