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
from core.exchange_init import exchange
from core.fail_stats_tracker import apply_failure_decay, get_symbol_risk_factor, schedule_failure_decay
from core.failure_logger import log_failure
from core.risk_utils import check_drawdown_protection

# ====== Новая "чистая" strategy ======
from core.strategy import last_trade_times, last_trade_times_lock, should_enter_trade

# ====== Торговый движок (без score) ======
from core.trade_engine import close_real_trade, enter_trade, trade_manager
from ip_monitor import start_ip_monitor
from missed_tracker import flush_best_missed_opportunities
from pair_selector import (
    auto_cleanup_signal_failures,
    auto_update_valid_pairs_if_needed,
    select_active_symbols,
    start_symbol_rotation,
    track_missed_opportunities,
)
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
from tools.continuous_scanner import continuous_scan, fetch_all_symbols
from tp_logger import ensure_log_exists
from tp_optimizer import run_tp_optimizer
from tp_optimizer_ml import analyze_and_optimize_tp
from utils_core import (
    get_cached_balance,
    get_runtime_config,
    initialize_cache,
    initialize_runtime_adaptive_config,
    load_state,
    normalize_symbol,
    reset_state_flags,
    save_state,
)
from utils_logging import add_log_separator, log

# Инициализация RISK_PERCENT (по желанию — если вам всё ещё нужно)
initialize_risk_percent()

# Глобальное событие для остановки
stop_event = threading.Event()


def get_trading_signal(symbol):
    """
    Генерирует торговый сигнал для указанного символа.
    Возвращает dict или None.
    """
    if isinstance(symbol, dict):
        symbol = symbol.get("symbol", "")

    symbol = normalize_symbol(symbol)

    try:
        # Вызываем should_enter_trade(...) для BUY и SELL
        buy_signal, buy_failures = should_enter_trade(symbol, exchange, last_trade_times, last_trade_times_lock)
        sell_signal, sell_failures = should_enter_trade(symbol, exchange, last_trade_times, last_trade_times_lock)

        if buy_signal is None and sell_signal is None:
            all_failures = list(set(buy_failures + sell_failures))
            log_failure(symbol, all_failures)
            return None

        # Если есть и BUY, и SELL — выбираем BUY
        if buy_signal and sell_signal:
            direction, qty, is_reentry, breakdown = buy_signal
        elif buy_signal:
            direction, qty, is_reentry, breakdown = buy_signal
        else:
            direction, qty, is_reentry, breakdown = sell_signal

        # Формируем итоговый dict для дальнейшей логики
        return {
            "side": direction,
            "qty": qty,
            "is_reentry": is_reentry,
            "breakdown": breakdown,
        }

    except Exception as e:
        log(f"[Signal] Error generating signal for {symbol}: {e}", level="ERROR")
        log_failure(symbol, ["exception", str(e)])
        return None


def load_symbols():
    """
    Получаем активные символы, иначе останавливаем бота
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
    Запуск фоновых потоков для отчётов
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
            # Воскресенье (weekday=6), 21:00
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
            # Каждые 2 дня в 21:30
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()  # tp_optimizer.py (простая оптимизация)
                    analyze_and_optimize_tp()  # tp_optimizer_ml.py (ML версия)
                else:
                    send_telegram_message("Not enough recent trades to optimize (min: 20)", force=True)
                time.sleep(60)
            time.sleep(10)

    # Запуск потоков
    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=extended_reports_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()


def check_block_health():
    """
    Мониторим risk_factor, при необходимости ускоряем decay
    """
    try:
        all_symbols = fetch_all_symbols()
        if not all_symbols:
            log("[HealthCheck] No symbols returned from fetch_all_symbols", level="WARNING")
            return

        high_risk_count = sum(1 for s in all_symbols if get_symbol_risk_factor(s)[0] < 0.25)
        ratio = high_risk_count / len(all_symbols)

        log(f"[HealthCheck] High risk symbols: {high_risk_count}/{len(all_symbols)} ({ratio:.1%})", level="INFO")

        if ratio > 0.3:
            log("[HealthCheck] ⚠️ Triggering accelerated decay (ratio>0.3)", level="WARNING")
            apply_failure_decay(accelerated=True)

            if ratio > 0.5:
                examples = [s for s in all_symbols if get_symbol_risk_factor(s)[0] < 0.25][:5]
                send_telegram_message(
                    f"🚨 Critical risk level: {high_risk_count}/{len(all_symbols)} symbols "
                    f"({ratio:.1%}) have high risk factors.\n"
                    f"Applying accelerated recovery.\n\n"
                    f"Examples: {', '.join(examples)}",
                    force=True,
                )
    except Exception as e:
        log(f"[HealthCheck] ❌ Error: {e}", level="ERROR")


def start_trading_loop():
    """
    Main trading loop
    """
    log("Starting BinanceBot main trading loop", level="INFO")

    # Статус бота -> running
    set_bot_status("running")
    initialize_cache()

    starting_balance = get_cached_balance()
    log(f"[Startup] Starting balance: {starting_balance:.2f} USDC", level="INFO", important=True)

    # Проверяем, нет ли «лишних» позиций
    positions = exchange.fetch_positions()
    active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
    if active_positions > MAX_POSITIONS:
        log(f"[Startup] Found {active_positions} positions > MAX_POSITIONS={MAX_POSITIONS}. Closing excess...", level="INFO")
        for pos in positions:
            if float(pos.get("contracts", 0)) != 0:
                symbol = pos["symbol"]
                close_real_trade(symbol)
                active_positions -= 1
                if active_positions <= MAX_POSITIONS:
                    break

    # Сброс state, сохраним
    state = load_state()
    state["stopping"] = False
    state["shutdown"] = False
    save_state(state)

    mode = "TESTNET" if USE_TESTNET else "REAL_RUN"
    if DRY_RUN:
        mode += " (DRY_RUN)"
    log(f"[Startup] Starting bot in {mode} mode...", important=True, level="INFO")

    # Уведомление Telegram
    message = f"Bot started in {mode} mode\n" f"Balance: {starting_balance:.2f} USDC\n" f"DRY_RUN: {DRY_RUN}, VERBOSE: {VERBOSE}"
    send_telegram_message(message, force=True, parse_mode="")

    # Обновим valидные пары, если нужно
    auto_update_valid_pairs_if_needed()

    symbols = load_symbols()
    if symbols:
        symbol_names = [item.get("symbol", "?") for item in symbols]
        log(f"[Startup] Loaded {len(symbols)} active symbols: {', '.join(symbol_names)}", important=True, level="INFO")
    else:
        log("[Startup] No active symbols loaded, exiting bot.", important=True, level="ERROR")
        return

    group_size = 5
    symbol_groups = [symbols[i : i + group_size] for i in range(0, len(symbols), group_size)]
    current_group_index = 0

    last_drawdown_check = 0
    trades_executed = 0

    try:
        while RUNNING and not stop_event.is_set():
            state = load_state()

            # Проверяем остановку бота
            if state.get("stopping") or state.get("shutdown"):
                from core.binance_api import get_open_positions

                open_positions = get_open_positions()
                if not open_positions:
                    # Всё закрыто
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
                    # Есть открытые позиции — закроем
                    syms_open = [pos["symbol"] for pos in open_positions]
                    msg = f"⏳ Still open positions ({len(open_positions)}): {', '.join(syms_open)}. Waiting..."
                    log(msg, level="INFO")
                    send_telegram_message(msg, force=True)

                    for pos in open_positions:
                        symbol = pos["symbol"]
                        log(f"[Stop] Closing position for {symbol}", level="INFO")
                        close_real_trade(symbol)
                        time.sleep(1)
                    time.sleep(10)
                    continue

            # Проверим, не превышен ли лимит позиций
            try:
                positions = exchange.fetch_positions()
                active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
                if active_positions >= MAX_POSITIONS:
                    log(f"[Main] Max open positions ({MAX_POSITIONS}) reached. Active: {active_positions}. Skipping cycle...", level="INFO")
                    time.sleep(30)
                    continue
                # Примеры «синхронизации» trade_manager
                if active_positions > 0 and not trade_manager._trades:
                    log(f"[Main] State mismatch: {active_positions} exchange positions, but trade_manager is empty. Force-closing all to sync...", level="WARNING")
                    for pos in positions:
                        if float(pos.get("contracts", 0)) != 0:
                            close_real_trade(pos["symbol"])
                    continue
            except Exception as e:
                log(f"[Main] Failed to fetch positions: {e}", level="ERROR")
                time.sleep(10)
                continue

            current_group = symbol_groups[current_group_index]

            if state.get("stopping") or stop_event.is_set():
                log("[Main] Stopping detected before trading cycle...", level="INFO")
                time.sleep(10)
                continue

            # Проверяем drawdown каждую минуту или после сделок
            balance = get_cached_balance()
            if not balance:
                log("Failed to fetch balance. Retrying in 30 seconds.", level="ERROR")
                time.sleep(30)
                continue

            now_ts = time.time()
            if now_ts - last_drawdown_check >= 60 or trades_executed > 0:
                drawdown_status = check_drawdown_protection(balance)
                last_drawdown_check = now_ts

                if drawdown_status["status"] == "paused":
                    log("Bot paused due to critical drawdown. Manual intervention required.", level="ERROR")
                    continue
                elif drawdown_status["status"] == "reduced_risk":
                    log(f"Risk reduced due to drawdown: {drawdown_status['drawdown']:.2f}%", level="WARNING")
                trades_executed = 0  # сбрасываем счётчик

            # Перебираем символы текущей группы
            for symbol in current_group:
                if stop_event.is_set():
                    log("[Main Loop] stop_event set, break group loop", level="INFO")
                    break
                try:
                    signal = get_trading_signal(symbol)
                    if signal:
                        side = signal["side"]
                        qty = signal["qty"]
                        is_reentry = signal.get("is_reentry", False)
                        breakdown = signal.get("breakdown", {})

                        log(f"[Main] Got trading signal for {symbol}: {side}, qty={qty:.4f}", level="INFO")
                        enter_trade(symbol, side, qty, is_reentry=is_reentry, breakdown=breakdown)
                        trades_executed += 1
                except Exception as e:
                    log(f"Error processing symbol {symbol}: {e}", level="ERROR")
                    continue

            # Переходим к следующей группе
            current_group_index = (current_group_index + 1) % len(symbol_groups)
            time.sleep(10)

        if not stop_event.is_set():
            log("[Main] RUNNING = False detected. Graceful shutdown triggered.", important=True, level="INFO")
            send_telegram_message("🛑 Bot stopped via graceful shutdown.", force=True, parse_mode="")

    except KeyboardInterrupt:
        log("[Main] Bot manually stopped (Ctrl+C)", important=True, level="INFO")
        send_telegram_message("🛑 Bot manually stopped (Ctrl+C)", force=True, parse_mode="")
        stop_event.set()


if __name__ == "__main__":
    add_log_separator()
    reset_state_flags()
    log("State flags reset at startup", level="INFO")

    # Гарантируем, что каталог data/ есть
    os.makedirs("data", exist_ok=True)

    # Проверяем файлы missed_opportunities.json, tp_performance.csv
    if not os.path.exists("data/missed_opportunities.json"):
        with open("data/missed_opportunities.json", "w") as f:
            f.write("{}")

    if not os.path.exists("data/tp_performance.csv"):
        with open("data/tp_performance.csv", "w") as f:
            f.write("Date,Symbol,Side,Entry Price,Exit Price,Qty,TP1 Hit,TP2 Hit,SL Hit," "PnL (%),Result,Held (min),Commission,Net PnL (%),Absolute Profit," "Type,ATR,Exit Reason\n")

    log("✅ Checked required data files", level="INFO")

    # Очищаем старые сигнал-фейлы
    auto_cleanup_signal_failures()

    # Инициализируем runtime config
    initialize_runtime_adaptive_config()
    log("✅ Adaptive config initialized", level="INFO")

    # Печатаем config
    config = get_runtime_config()
    log(f"Runtime config at startup: {config}", level="DEBUG")

    # Запоминаем время старта
    state = load_state()
    current_time = time.time()
    state["session_start_time"] = current_time
    save_state(state)
    log(f"🟢 Bot session started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}", level="INFO")

    ensure_log_exists()

    schedule_failure_decay()
    log("✅ Initial failure decay scheduled", level="INFO")

    log("Running initial continuous scan...", level="INFO")
    continuous_scan()

    scheduler = BackgroundScheduler()

    # Пример ротации
    def rotate_symbols():
        syms = select_active_symbols()
        log(f"🔁 Symbol re-rotation. {len(syms)} pairs loaded.", level="INFO")

    scheduler.add_job(rotate_symbols, "interval", minutes=30, id="symbol_rotation")

    import ip_monitor

    ip_monitor.boot_time = time.time()

    # Запускаем поток обработки команд Telegram
    threading.Thread(
        target=lambda: process_telegram_commands(state, lambda msg, st: telegram_commands.handle_telegram_command(msg, st, stop_event=stop_event)),
        daemon=True,
    ).start()

    # Запускаем мониторинг IP
    threading.Thread(
        target=lambda: start_ip_monitor(
            lambda: telegram_commands._initiate_stop("ip_changed", stop_event=stop_event),
            interval_seconds=IP_MONITOR_INTERVAL_SECONDS,
        ),
        daemon=True,
    ).start()

    # Ротация символов, отчётные потоки
    threading.Thread(target=lambda: start_symbol_rotation(stop_event), daemon=True).start()
    threading.Thread(target=start_report_loops, daemon=True).start()

    from core.risk_adjuster import auto_adjust_risk  # ✅ добавлено
    from core.status_logger import log_symbol_activity_status

    scheduler.add_job(send_daily_summary, "cron", hour=23, minute=59)
    scheduler.add_job(analyze_and_optimize_tp, "cron", day_of_week="sun", hour=10)
    scheduler.add_job(track_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(flush_best_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(auto_adjust_relax_factors_from_missed, "interval", minutes=30)
    scheduler.add_job(schedule_failure_decay, "interval", hours=1, id="failure_decay")
    scheduler.add_job(continuous_scan, "interval", minutes=15, id="symbol_scanner")
    scheduler.add_job(check_block_health, "interval", minutes=30, id="risk_health_check")
    scheduler.add_job(log_symbol_activity_status, "interval", minutes=10, id="status_logger")

    scheduler.add_job(auto_adjust_risk, "interval", hours=1, id="risk_adjuster")

    from core.fail_stats_tracker import migrate_from_blocked_symbols

    migrate_from_blocked_symbols()
    log("✅ Migrated from old blocking to graduated risk system", level="INFO")

    from common.config_loader import ENABLE_FULL_DEBUG_MONITORING
    from debug_tools import run_monitor

    if ENABLE_FULL_DEBUG_MONITORING:
        log("✅ ENABLE_FULL_DEBUG_MONITORING is True — starting diagnostic audit", level="INFO")
        run_monitor()

    scheduler.start()
    log("✅ Scheduler started (daily summary, symbol rotation, missed ops, etc.)", level="INFO")

    try:
        start_trading_loop()
    finally:
        if scheduler.running:
            scheduler.shutdown()
            log("Scheduler shutdown completed", level="INFO")
