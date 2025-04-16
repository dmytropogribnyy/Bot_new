from config import DRY_RUN, MAX_POSITIONS, MIN_NOTIONAL, SL_PERCENT
from core.order_utils import calculate_order_quantity
from core.risk_utils import get_adaptive_risk_percent
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
    dry_run_positions_count,
    get_position_size,
    open_positions_count,
    open_positions_lock,
)

# Исправлено: utils.core -> utils_core, удалён get_adaptive_risk_percent
from utils_logging import log


def process_symbol(symbol, balance, last_trade_times, lock):
    try:
        # Используем фиксированное значение для теста
        max_open_positions = MAX_POSITIONS
        with open_positions_lock:
            active_count = dry_run_positions_count if DRY_RUN else open_positions_count
            if active_count >= max_open_positions:
                log(
                    f"⏩ Skipping {symbol} — max open positions ({max_open_positions}) reached",
                    level="DEBUG",
                )
                return None

        if get_position_size(symbol) > 0:
            log(f"⏩ Skipping {symbol} — already in position", level="DEBUG")
            return None

        df = fetch_data(symbol)
        if df is None:
            log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
            return None

        result = should_enter_trade(symbol, df, None, last_trade_times, lock)
        if result is None:
            log(f"❌ No signal for {symbol}", level="DEBUG")
            return None

        # Распаковываем кортеж из should_enter_trade
        direction, score, is_reentry = result
        entry = df["close"].iloc[-1]
        stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
        risk_percent = get_adaptive_risk_percent(balance)
        qty = calculate_order_quantity(entry, stop, balance, risk_percent)

        if qty * entry < MIN_NOTIONAL:
            log(f"⚠️ Notional too low for {symbol} — skipping", level="WARNING")
            return None

        log(
            f"{symbol} 🔍 Calculated qty: {qty:.3f}, entry: {entry:.2f}, notional: {qty * entry:.2f}",
            level="DEBUG",
        )

        return {
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry": entry,
            "score": score,
            "is_reentry": is_reentry,
        }
    except Exception as e:
        log(f"🔥 Error in process_symbol for {symbol}: {e}", level="ERROR")
        return None
