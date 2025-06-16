"""
Main trading loop for BinanceBot
Manages the core trading cycle, risk management, and drawdown protection
"""

import json
import os
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from common.config_loader import (
    DRY_RUN,
    RUNNING,
    USE_TESTNET,
    set_bot_status,
)
from core.exchange_init import exchange
from core.fail_stats_tracker import (
    apply_failure_decay,
    get_symbol_risk_factor,
    migrate_from_blocked_symbols,
    schedule_failure_decay,
)
from core.failure_logger import log_failure
from core.strategy import last_trade_times, last_trade_times_lock, should_enter_trade
from core.trade_engine import close_real_trade, trade_manager
from missed_tracker import flush_best_missed_opportunities
from pair_selector import auto_cleanup_signal_failures, auto_update_valid_pairs_if_needed, select_active_symbols, start_symbol_rotation, track_missed_opportunities
from stats import (
    generate_daily_report,
    send_halfyear_report,
    send_monthly_report,
    send_quarterly_report,
    send_weekly_report,
    send_yearly_report,
    should_run_optimizer,
)
from telegram.telegram_commands import handle_telegram_command
from telegram.telegram_handler import process_telegram_commands
from telegram.telegram_utils import send_daily_summary, send_telegram_message
from tools.continuous_scanner import continuous_scan, fetch_all_symbols
from tp_logger import ensure_log_exists
from tp_optimizer import run_tp_optimizer
from utils_core import (
    get_cached_balance,
    initialize_cache,
    initialize_runtime_adaptive_config,
    load_state,
    normalize_symbol,
    reset_state_flags,
    save_state,
)
from utils_logging import add_log_separator, log

# Опциональная инициализация
stop_event = threading.Event()


def restore_active_trades():
    """
    Восстанавливает активные сделки из data/active_trades.json при старте бота.
    Удаляет записи, по которым позиции на Binance уже закрыты.
    """
    from core.trade_engine import get_position_size

    file_path = Path("data/active_trades.json")
    if not file_path.exists():
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            trades = json.load(f)

        restored = 0
        still_open = {}

        for symbol, trade_data in trades.items():
            if get_position_size(symbol) > 0:
                trade_manager.add_trade(symbol, trade_data)
                still_open[symbol] = trade_data
                restored += 1
            else:
                log(f"[Startup] Skipping {symbol} — position not open on Binance", level="INFO")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(still_open, f, indent=2)

        if restored > 0:
            send_telegram_message(f"♻️ Restored {restored} active trades from file", force=True)
            log(f"[Startup] Restored {restored} trades from active_trades.json", level="INFO")
        else:
            log("[Startup] No valid active trades to restore", level="INFO")

    except Exception as e:
        log(f"[Startup] Failed to restore active trades: {e}", level="ERROR")


def get_trading_signal(symbol):
    """
    Генерирует торговый сигнал по символу с логированием причин отказа.
    """

    if isinstance(symbol, dict):
        symbol = symbol.get("symbol", "")
    symbol = normalize_symbol(symbol)

    try:
        buy_signal, buy_failures = should_enter_trade(symbol, exchange, last_trade_times, last_trade_times_lock)

        if buy_signal is None:
            log(f"[Signal] ❌ No signal for {symbol} | Reasons: {buy_failures}", level="DEBUG")
            log_failure(symbol, buy_failures)
            return None

        direction, qty, is_reentry, breakdown = buy_signal

        log(f"[Signal] ✅ Signal generated for {symbol} | dir={direction}, qty={qty:.3f}, reentry={is_reentry}", level="DEBUG")
        log(f"[Signal] 🔍 Breakdown: {breakdown}", level="DEBUG")

        return {
            "side": direction,
            "qty": qty,
            "is_reentry": is_reentry,
            "breakdown": breakdown,
        }

    except Exception as e:
        log(f"[Signal] ❌ Exception generating signal for {symbol}: {e}", level="ERROR")
        log_failure(symbol, ["exception", str(e)])
        return None


def load_symbols():
    """
    Загружает активные пары или завершает бот, если пусто.
    """
    symbols = select_active_symbols()
    if not symbols:
        log("No active symbols loaded, stopping bot", level="ERROR")
        send_telegram_message("⚠️ No active symbols loaded. Stopping bot.", force=True)
        stop_event.set()
        return []
    return symbols


def start_report_loops():
    """
    Запускает фоновые потоки для ежедневных и расширенных отчётов.
    """

    def daily_loop():
        while not stop_event.is_set():
            now = datetime.now()
            if now.hour == 21 and now.minute == 0:
                generate_daily_report()
                time.sleep(60)
            time.sleep(10)

    def weekly_loop():
        while not stop_event.is_set():
            now = datetime.now()
            if now.weekday() == 6 and now.hour == 21 and now.minute == 0:
                send_weekly_report()
                time.sleep(60)
            time.sleep(10)

    def extended_loop():
        while not stop_event.is_set():
            now = datetime.now()
            if now.day == 1:
                if now.hour == 21 and now.minute == 0:
                    send_monthly_report()
                if now.month in [1, 4, 7, 10] and now.minute == 5:
                    send_quarterly_report()
                if now.month in [1, 7] and now.minute == 10:
                    send_halfyear_report()
                if now.month == 1 and now.minute == 15:
                    send_yearly_report()
            time.sleep(10)

    def optimizer_loop():
        while not stop_event.is_set():
            now = datetime.now()
            if now.day % 2 == 0 and now.hour == 21 and now.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                else:
                    send_telegram_message("Not enough recent trades to optimize (min: 20)", force=True)
                time.sleep(60)
            time.sleep(10)

    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=extended_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()


def check_block_health():
    from core.failure_logger import log_failure
    from tp_logger import TP_LOG_FILE
    from utils_core import load_json_file

    try:
        all_symbols = fetch_all_symbols()
        if not all_symbols:
            log("[HealthCheck] No symbols returned", level="WARNING")
            return

        high_risk = [s for s in all_symbols if get_symbol_risk_factor(s)[0] < 0.25]
        ratio = len(high_risk) / len(all_symbols)
        log(f"[HealthCheck] High risk: {len(high_risk)}/{len(all_symbols)} ({ratio:.1%})", level="INFO")

        # 🔄 Логируем их как провальные — для накопления статистики
        for sym in high_risk:
            log_failure(sym, ["high_risk_auto"])

        if ratio > 0.3:
            apply_failure_decay(accelerated=True)
            log("Accelerated decay triggered", level="WARNING")

            # 🟠 При >50% — Telegram alert + PnL
            if ratio > 0.5:
                examples = high_risk[:5]

                # 📊 Считаем последние 20 сделок и средний PnL
                try:
                    df = load_json_file(TP_LOG_FILE, fallback=[])
                    if isinstance(df, list):
                        import pandas as pd

                        df = pd.DataFrame(df)
                    if not df.empty:
                        df_recent = df.tail(20)
                        pnl_avg = round(df_recent["PnL (%)"].mean(), 2)
                        trades_count = len(df_recent)
                    else:
                        pnl_avg = None
                        trades_count = 0
                except Exception as e:
                    pnl_avg = None
                    trades_count = 0
                    log(f"[HealthCheck] Error reading TP log: {e}", level="WARNING")

                msg = f"🚨 High risk level: {len(high_risk)}/{len(all_symbols)} ({ratio:.1%})\n" f"Accelerated recovery triggered\n" f"Examples: {', '.join(examples)}"
                if pnl_avg is not None:
                    msg += f"\n📉 Avg PnL (last {trades_count}): {pnl_avg:.2f}%"

                send_telegram_message(msg, force=True)

    except Exception as e:
        log(f"[HealthCheck] Error: {e}", level="ERROR")


def start_trading_loop():
    from core.binance_api import get_open_positions
    from core.engine_controller import run_trading_cycle

    # === Force loading market info (for minNotional etc.)
    from core.exchange_init import exchange
    from utils_core import get_runtime_config

    exchange.load_markets()
    log("[Startup] exchange.load_markets() completed", level="DEBUG")

    # === Force refresh positions cache
    from utils_core import api_cache

    api_cache["positions"]["timestamp"] = 0
    log("[Startup] positions cache invalidated", level="DEBUG")

    # === Инициализация ===
    set_bot_status("running")
    initialize_cache()

    restore_active_trades()

    start_balance = get_cached_balance()
    log(f"[Startup] Start balance: {start_balance:.2f} USDC", level="INFO")

    # === Лог runtime_config ===
    runtime_config = get_runtime_config()
    log(
        f"[Config] Loaded runtime_config: "
        f"max_positions={runtime_config.get('max_concurrent_positions')}, "
        f"SL={runtime_config.get('SL_PERCENT')*100:.2f}%, "
        f"TP1~{runtime_config.get('auto_profit_threshold')}%, "
        f"hold_time={runtime_config.get('max_hold_minutes')}min, "
        f"volume≥{runtime_config.get('volume_threshold_usdc')} USDC, "
        f"ATR≥{runtime_config.get('atr_threshold_percent')*100:.2f}%",
        level="INFO",
    )

    # === Обнуление флагов состояния ===
    state = load_state()
    state["stopping"] = False
    state["shutdown"] = False
    save_state(state)

    # === Telegram стартовое сообщение ===
    mode = "TESTNET" if USE_TESTNET else "REAL_RUN"
    if DRY_RUN:
        mode += " (DRY_RUN)"
    send_telegram_message(
        f"🚀 Bot started: {mode}\n"
        f"Balance: {start_balance:.2f} USDC\n"
        f"Max Positions: {runtime_config.get('max_concurrent_positions')}\n"
        f"SL: {runtime_config.get('SL_PERCENT')*100:.2f}%, TP1~{runtime_config.get('auto_profit_threshold')}%",
        force=True,
    )

    # === Получение символов ===
    auto_update_valid_pairs_if_needed()
    symbols = load_symbols()
    symbols = [normalize_symbol(s) for s in symbols]  # ✅ Нормализация
    if not symbols:
        send_telegram_message("⚠️ No symbols loaded for trading. Bot will not run.", force=True)
        return

    log(f"[Startup] Loaded {len(symbols)} symbols for trading", level="INFO")

    # === Telegram-лог списка загруженных пар ===
    from common.config_loader import FIXED_PAIRS

    fixed_set = set([s.replace("/", "").upper() for s in FIXED_PAIRS])
    symbol_log = []
    for sym in symbols:
        norm = sym.replace("/", "").upper()
        tag = "🧷F" if norm in fixed_set else "🔁D"
        symbol_log.append(f"{tag} {norm}")

    msg = "📊 Active Pairs Loaded:\n" + "\n".join(symbol_log)
    send_telegram_message(msg, force=True)

    # ✅ Очистка cooldown таймеров (важно!)
    from core.runtime_state import last_trade_times, last_trade_times_lock

    with last_trade_times_lock:
        last_trade_times.clear()
        log("[Cooldown] Reset last_trade_times on new run", level="DEBUG")

    try:
        while RUNNING and not stop_event.is_set():
            # === Стоп и выход при закрытых всех позициях ===
            if load_state().get("stopping") or stop_event.is_set():
                open_pos = get_open_positions()
                if not open_pos:
                    send_telegram_message("✅ No open positions. Bot exiting.", force=True)
                    return
                for pos in open_pos:
                    close_real_trade(pos["symbol"])
                    time.sleep(1)
                continue

            # === Запуск торгового цикла ===
            run_trading_cycle(symbols, stop_event)
            time.sleep(10)

    except KeyboardInterrupt:
        from core.trade_engine import handle_panic

        log("🚩 Manual stop (Ctrl+C)", level="INFO")
        send_telegram_message("🚩 Bot manually stopped. Initiating panic close...", force=True)
        stop_event.set()
        handle_panic(stop_event)


if __name__ == "__main__":
    # === Стартовый лог и подготовка окружения ===
    add_log_separator()
    reset_state_flags()
    os.makedirs("data", exist_ok=True)
    log("📦 Runtime environment initialized", level="INFO")

    # === Убедимся, что все ключевые файлы существуют ===
    Path("data/missed_opportunities.json").write_text("{}", encoding="utf-8") if not Path("data/missed_opportunities.json").exists() else None

    if not Path("data/tp_performance.csv").exists():
        with open("data/tp_performance.csv", "w", encoding="utf-8") as f:
            f.write("timestamp,symbol,side,entry,exit,qty,pnl_percent,result,tp1_hit,tp2_hit,sl_hit,commission\n")

    # === Инициализация конфигураций и адаптаций ===
    auto_cleanup_signal_failures()
    initialize_runtime_adaptive_config()
    ensure_log_exists()
    schedule_failure_decay()
    continuous_scan()
    migrate_from_blocked_symbols()

    # === Обновляем символы и только после — debug_monitor
    auto_update_valid_pairs_if_needed()
    symbols = load_symbols()
    symbols = [normalize_symbol(s) for s in symbols]
    if not symbols:
        exit(1)

    from debug_tools import run_monitor

    threading.Thread(target=run_monitor, daemon=True).start()

    # === Запоминаем старт сессии ===
    state = load_state()
    state["session_start_time"] = time.time()
    save_state(state)

    # === Планировщик (APScheduler) ===
    scheduler = BackgroundScheduler(job_defaults={"max_instances": 3})
    scheduler.add_job(send_daily_summary, "cron", hour=23, minute=59)
    scheduler.add_job(track_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(flush_best_missed_opportunities, "interval", minutes=30)
    scheduler.add_job(schedule_failure_decay, "interval", hours=1)
    scheduler.add_job(continuous_scan, "interval", minutes=15)
    scheduler.add_job(check_block_health, "interval", minutes=30)
    scheduler.add_job(run_monitor, "interval", minutes=15)

    from core.risk_adjuster import auto_adjust_risk

    scheduler.add_job(auto_adjust_risk, "interval", hours=1)

    # === Telegram и фоновая логика ===
    threading.Thread(
        target=lambda: process_telegram_commands(state, lambda msg, st: handle_telegram_command(msg, st, stop_event)),
        daemon=True,
    ).start()
    threading.Thread(target=lambda: start_symbol_rotation(stop_event), daemon=True).start()
    threading.Thread(target=start_report_loops, daemon=True).start()

    # === Обработка Ctrl+C / SIGTERM ===
    def handle_exit_signal(signum, frame):
        log("🛑 Termination signal", level="WARNING")
        stop_event.set()
        if scheduler.running:
            scheduler.shutdown()
            log("🛑 Scheduler stopped", level="INFO")

    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    scheduler.start()
    log("✅ Scheduler started", level="INFO")

    try:
        start_trading_loop()
    finally:
        if scheduler.running:
            scheduler.shutdown()
            log("🛑 Bot shutdown complete", level="INFO")
