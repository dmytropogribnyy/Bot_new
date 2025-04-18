from config import LEVERAGE_MAP, MAX_POSITIONS, MIN_NOTIONAL, RISK_PERCENT, SL_PERCENT
from core.exchange_init import exchange
from core.order_utils import calculate_order_quantity
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import (
    get_position_size,
    open_positions_lock,
)
from utils_logging import log


def process_symbol(symbol, balance, last_trade_times, lock):
    try:
        with open_positions_lock:
            positions = exchange.fetch_positions()
            active_positions = sum(1 for pos in positions if float(pos.get("contracts", 0)) != 0)
            if active_positions >= MAX_POSITIONS:
                log(
                    f"⏩ Skipping {symbol} — max open positions ({MAX_POSITIONS}) reached (current: {active_positions})",
                    level="DEBUG",
                )
                return None

            if get_position_size(symbol) > 0:
                log(f"⏩ Skipping {symbol} — already in position", level="DEBUG")
                return None

            # Check available margin
            balance_info = exchange.fetch_balance()
            available_margin = float(balance_info["info"]["availableMargin"])
            df = fetch_data(symbol)
            if df is None:
                log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
                return None

            result = should_enter_trade(symbol, df, None, last_trade_times, lock)
            if result is None:
                log(f"❌ No signal for {symbol}", level="DEBUG")
                return None

            direction, score, is_reentry = result
            entry = df["close"].iloc[-1]
            stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
            qty = calculate_order_quantity(entry, stop, balance, RISK_PERCENT)

            required_margin = qty * entry / LEVERAGE_MAP.get(symbol, 5)
            if required_margin > available_margin:
                log(
                    f"⚠️ Skipping {symbol} — insufficient margin (required: {required_margin:.2f}, available: {available_margin:.2f})",
                    level="WARNING",
                )
                return None

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
