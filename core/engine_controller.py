# core/engine_controller.py

import os
import threading

from core.exchange_init import exchange

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def run_trading_cycle(symbols, stop_event):
    """
    Торговый цикл:
      1) Проверка drawdown, stopping/shutdown
      2) Установка плечей (если список изменился)
      3) Проверка лимитов позиций
      4) Обработка каждого symbol через process_symbol()
      5) Вход через enter_trade при наличии сигнала
      6) Учитываются анти-reentry, блокировки, лимиты в час
    """
    import traceback

    from common.config_loader import AUTO_PROFIT_ENABLED, DRY_RUN
    from common.leverage_config import set_leverage_for_symbols
    from core.entry_logger import log_entry
    from core.notifier import notify_dry_trade
    from core.position_manager import get_max_positions
    from core.risk_guard import is_symbol_blocked, is_symbol_recently_traded, update_symbol_last_entry
    from core.risk_utils import check_drawdown_protection
    from core.runtime_state import last_trade_times, last_trade_times_lock
    from core.runtime_stats import is_hourly_limit_reached, update_trade_count
    from core.symbol_processor import process_symbol
    from core.trade_engine import check_auto_profit, enter_trade, get_position_size, safe_close_trade, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_core import get_cached_balance, get_cached_positions, load_state, normalize_symbol
    from utils_logging import log, notify_error

    if not symbols:
        log("[engine_controller] No symbols provided to trading cycle", level="WARNING")
        return

    # === Drawdown check ===
    balance = get_cached_balance()
    drawdown_status = check_drawdown_protection(balance)
    if drawdown_status["status"] == "paused":
        log("[Risk] Trading paused due to drawdown protection", level="WARNING")
        return
    if drawdown_status["status"] == "reduced_risk":
        log("[Risk] Reduced risk mode active due to drawdown", level="INFO")

    state = load_state()

    # === Установка плеч при первом вызове или смене списка символов ===
    if not hasattr(run_trading_cycle, "last_symbols") or run_trading_cycle.last_symbols != symbols:
        log("[engine_controller] Setting leverage for symbols (list changed)", level="DEBUG")
        set_leverage_for_symbols()
        run_trading_cycle.last_symbols = symbols.copy()

    max_positions = get_max_positions(balance)
    positions = get_cached_positions()
    active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)

    # === Проверка режима остановки
    if state.get("stopping"):
        open_trades = sum(get_position_size(sym) > 0 for sym in symbols)
        log(f"[engine_controller] Open trades count: {open_trades}", level="DEBUG")
        if open_trades == 0:
            log("[engine_controller] All positions closed — stopping bot.", level="INFO")
            send_telegram_message("✅ All positions closed. Bot stopped.", force=True)
            if state.get("shutdown"):
                log("[engine_controller] Shutdown flag → exiting fully.", level="INFO")
                os._exit(0)
        else:
            log(f"[engine_controller] Waiting for {open_trades} open positions...", level="INFO")
        return

    if active_positions >= max_positions:
        log(f"[engine_controller] Max positions ({max_positions}) reached. Active: {active_positions}.", level="INFO")
        return

    # === Статистика входов ===
    entry_attempts = 0
    entry_successes = 0

    # === Основной цикл по символам ===
    for symbol in symbols:
        symbol = normalize_symbol(symbol)

        if stop_event and stop_event.is_set():
            log(f"[Trading Cycle] Stop signal set — skipping {symbol}.", level="DEBUG")
            continue

        positions = get_cached_positions()
        current_active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)
        if current_active_positions >= max_positions:
            log(f"[engine_controller] Max positions ({max_positions}) reached mid-cycle. Stop scanning.", level="INFO")
            break

        try:
            log(f"[engine_controller] Checking {symbol}", level="DEBUG")

            # === AutoProfit
            current_trade = trade_manager.get_trade(symbol)
            if AUTO_PROFIT_ENABLED and current_trade:
                if check_auto_profit(current_trade):
                    log(f"[engine_controller] AutoProfit => close {symbol}", level="INFO")
                    safe_close_trade(exchange, symbol, current_trade, reason="auto_profit")
                    continue

            if is_symbol_recently_traded(symbol):
                log(f"[engine_controller] Skipping {symbol} — recent trade entry", level="DEBUG")
                continue

            if is_symbol_blocked(symbol):
                log(f"[engine_controller] Skipping {symbol} — currently blocked", level="INFO")
                continue

            if is_hourly_limit_reached():
                log(f"[engine_controller] Max hourly trade limit — skip {symbol}", level="INFO")
                continue

            # === Основная логика входа
            entry_attempts += 1
            trade_data = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade_data:
                continue
            entry_successes += 1

            is_reentry = trade_data.get("is_reentry", False)

            if DRY_RUN:
                notify_dry_trade(trade_data)
                log_entry(trade_data, status="SUCCESS")

            # 🔧 Фикс: передаём все аргументы по именам
            enter_trade(
                symbol=trade_data["symbol"],
                side=trade_data["direction"],
                is_reentry=is_reentry,
                breakdown=trade_data.get("breakdown"),
                pair_type=trade_data.get("pair_type", "unknown"),
            )

            if not DRY_RUN:
                log_entry(trade_data, status="SUCCESS")
                update_symbol_last_entry(symbol)
                update_trade_count()

        except Exception as e:
            tb = traceback.format_exc(limit=1)
            notify_error(f"🔥 Error during {symbol}: {e}")
            log(f"[engine_controller] Error in trading cycle for {symbol}: {e}\n{tb}", level="ERROR")
            continue

    # ✅ Desync check (FIX-6) в конец цикла
    try:
        binance_positions = exchange.fetch_positions()
        open_symbols = [p["symbol"] for p in binance_positions if float(p.get("contracts", 0)) > 0]

        for symbol in open_symbols:
            if symbol not in trade_manager.get_active_trades():
                log(f"[Desync] Binance open position {symbol} not in trade_manager!", level="ERROR")
                send_telegram_message(f"🚨 DESYNC: Binance has position {symbol}, but bot does not.")
    except Exception as e:
        log(f"[Desync] Failed to check positions: {e}", level="WARNING")

    log(f"[Entry Stats] Attempted={entry_attempts}, Valid={entry_successes}, Symbols={len(symbols)}", level="INFO")


def soft_exit_trade(symbol: str, reason: str = "soft_exit"):
    """
    Плавно закрывает позицию по symbol. Если ошибка — помечает как pending_exit.
    Не вызывает record_trade_result при reason='error'.
    """
    from core.trade_engine import close_real_trade, trade_manager
    from telegram.telegram_utils import send_telegram_message
    from utils_logging import log

    trade = trade_manager.get_trade(symbol)
    if not trade:
        log(f"[SoftExit] No active trade for {symbol}", level="WARNING")
        return

    try:
        log(f"[SoftExit] Attempting soft exit for {symbol}, reason={reason}", level="INFO")

        if reason == "error":
            log(f"[SoftExit] Error reason for {symbol}, skipping finalization", level="WARNING")
            trade["pending_exit"] = True
            trade_manager.update_trade(symbol, trade)
            send_telegram_message(f"⚠️ Soft exit error for {symbol}. Marked as pending_exit.")
            return

        # Иначе — обычное закрытие
        close_real_trade(symbol)
        log(f"[SoftExit] Completed soft exit for {symbol}", level="INFO")

    except Exception as e:
        log(f"[SoftExit] ❌ Failed to close {symbol}: {e}", level="ERROR")
        trade["pending_exit"] = True
        trade_manager.update_trade(symbol, trade)
        send_telegram_message(f"⚠️ Soft exit failed for {symbol}. Marked as pending_exit.", force=True)
