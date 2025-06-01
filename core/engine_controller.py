# core/engine_controller.py

import os
import threading

from entry_logger import log_entry

from common.config_loader import (
    DRY_RUN,
)
from core.exchange_init import exchange
from core.notifier import notify_dry_trade, notify_error
from core.risk_utils import get_max_positions
from telegram.telegram_utils import send_telegram_message
from utils_core import (
    get_cached_balance,
    get_cached_positions,
    load_state,
    set_leverage_for_symbols,
)
from utils_logging import log

last_trade_times = {}
last_trade_times_lock = threading.Lock()


def run_trading_cycle(symbols, stop_event):
    """
    Упрощённый цикл без score/HTF:
      1) Проверка stopping/shutdown
      2) Ставим плечи (разово, если список символов поменялся)
      3) Проверяем max_positions
      4) Для каждого symbol вызываем process_symbol()
      5) Если вернулись trade_data → enter_trade()
    """
    from trade_engine import (
        check_auto_profit,
        enter_trade,
        get_position_size,
        safe_close_trade,
        trade_manager,
    )

    from common.config_loader import AUTO_PROFIT_ENABLED
    from core.symbol_processor import process_symbol

    if not symbols:
        log("[engine_controller] No symbols provided to trading cycle", level="WARNING")
        return

    state = load_state()

    # Ставим плечи, если символы изменились
    if not hasattr(run_trading_cycle, "last_symbols") or run_trading_cycle.last_symbols != symbols:
        log("[engine_controller] Setting leverage for symbols (list changed)", level="DEBUG")
        set_leverage_for_symbols()
        run_trading_cycle.last_symbols = symbols.copy()

    balance = get_cached_balance()
    max_positions = get_max_positions(balance)

    # Проверка режима остановки
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

    positions = get_cached_positions()
    active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)
    if active_positions >= max_positions:
        log(f"[engine_controller] Max positions ({max_positions}) reached. Active: {active_positions}.", level="INFO")
        return

    # Проходим по символам
    for symbol in symbols:
        if stop_event.is_set():
            log(f"[Trading Cycle] Stop signal → abort cycle for {symbol}.", level="INFO")
            break

        # Повторная проверка свободных слотов
        positions = get_cached_positions()
        current_active_positions = sum(float(pos.get("contracts", 0)) > 0 for pos in positions)
        if current_active_positions >= max_positions:
            log(f"[engine_controller] Max positions ({max_positions}) reached mid-cycle. Stop scanning.", level="INFO")
            break

        try:
            log(f"[engine_controller] Checking {symbol}", level="DEBUG")

            # Авто-profit (ранний выход)
            current_trade = trade_manager.get_trade(symbol)
            if AUTO_PROFIT_ENABLED and current_trade:
                if check_auto_profit(current_trade):
                    log(f"[engine_controller] AutoProfit => close {symbol}", level="INFO")
                    safe_close_trade(exchange, symbol, current_trade, reason="auto_profit")
                    continue

            # process_symbol(...) возвращает trade_data?
            trade_data = process_symbol(symbol, balance, last_trade_times, last_trade_times_lock)
            if not trade_data:
                # Ничего не открываем
                continue

            # Если там есть score — удаляем (не нужно)
            if "score" in trade_data:
                del trade_data["score"]

            # Передаём is_reentry в enter_trade
            is_reentry = trade_data.get("is_reentry", False)

            # DRY_RUN logging
            if DRY_RUN:
                notify_dry_trade(trade_data)
                log_entry(trade_data, status="SUCCESS", mode="DRY_RUN")

            # Пример: прокидываем pair_type
            # enter_trade(..., pair_type=trade_data.get("pair_type", "unknown"))
            enter_trade(trade_data["symbol"], trade_data["direction"], trade_data["qty"], is_reentry=is_reentry, pair_type=trade_data.get("pair_type", "unknown"))
            if not DRY_RUN:
                log_entry(trade_data, status="SUCCESS", mode="REAL_RUN")

        except Exception as e:
            notify_error(f"🔥 Error during {symbol}: {str(e)}")
            log(f"[engine_controller] Error in trading cycle for {symbol}: {e}", level="ERROR")
