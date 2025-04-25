from config import (
    LEVERAGE_MAP,
    MAX_POSITIONS,
    MIN_NOTIONAL_OPEN,  # Updated import
    RISK_PERCENT,
    SL_PERCENT,
)
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
            margin_info = balance_info["info"]
            total_margin_balance = float(margin_info.get("totalMarginBalance", 0))
            position_initial_margin = float(margin_info.get("totalPositionInitialMargin", 0))
            open_order_initial_margin = float(margin_info.get("totalOpenOrderInitialMargin", 0))
            available_margin = (
                total_margin_balance - position_initial_margin - open_order_initial_margin
            )
            if available_margin <= 0:
                log(
                    f"⚠️ Skipping {symbol} — no available margin (total: {total_margin_balance:.2f}, positions: {position_initial_margin:.2f}, orders: {open_order_initial_margin:.2f})",
                    level="ERROR",
                )
                return None

            df = fetch_data(symbol)
            if df is None:
                log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
                return None

            result = should_enter_trade(symbol, df, exchange, last_trade_times, lock)
            if result is None:
                log(f"❌ No signal for {symbol}", level="DEBUG")
                return None

            direction, score, is_reentry = result
            entry = df["close"].iloc[-1]
            stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
            qty = calculate_order_quantity(entry, stop, balance, RISK_PERCENT)

            # Normalize symbol format to match LEVERAGE_MAP (e.g., 'XRP/USDC:USDC' -> 'XRP/USDC')
            normalized_symbol = symbol.split(":")[0] if ":" in symbol else symbol

            required_margin = qty * entry / LEVERAGE_MAP.get(normalized_symbol, 5)
            if required_margin > available_margin:
                log(
                    f"⚠️ Skipping {symbol} — insufficient margin (required: {required_margin:.2f}, available: {available_margin:.2f})",
                    level="WARNING",
                )
                return None

            # Check notional requirement for opening a position
            notional = qty * entry
            if notional < MIN_NOTIONAL_OPEN:
                log(
                    f"⚠️ Notional too low for {symbol} — notional: {notional:.2f}, required: {MIN_NOTIONAL_OPEN:.2f}, skipping",
                    level="WARNING",
                )
                return None

            log(
                f"{symbol} 🔍 Calculated qty: {qty:.3f}, entry: {entry:.2f}, notional: {notional:.2f}",
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
