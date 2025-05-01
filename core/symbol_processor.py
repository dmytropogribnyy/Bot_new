from config import (
    LEVERAGE_MAP,
    MAX_POSITIONS,
    MIN_NOTIONAL_OPEN,
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
from telegram.telegram_utils import send_telegram_message
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
                send_telegram_message(f"⚠️ No available margin for {symbol}", force=True)
                return None

            df = fetch_data(symbol)
            if df is None:
                log(f"⚠️ Skipping {symbol} — fetch_data returned None", level="WARNING")
                send_telegram_message(f"⚠️ Failed to fetch data for {symbol}", force=True)
                return None

            result = should_enter_trade(symbol, df, exchange, last_trade_times, lock)
            if result is None:
                log(f"❌ No signal for {symbol}", level="DEBUG")
                return None

            direction, score, is_reentry = result
            entry = df["close"].iloc[-1]
            stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
            qty = calculate_order_quantity(entry, stop, balance, RISK_PERCENT)

            # Проверка на None
            if any(v is None for v in [entry, stop, qty]):
                log(
                    f"⚠️ Skipping {symbol} — invalid input data (entry={entry}, stop={stop}, qty={qty})",
                    level="ERROR",
                )
                send_telegram_message(f"⚠️ Invalid input data for {symbol}", force=True)
                return None

            # Normalize symbol format to match LEVERAGE_MAP (e.g., 'BTC/USDT:USDT' -> 'BTCUSDT')
            normalized_symbol = (
                symbol.split(":")[0].replace("/", "") if ":" in symbol else symbol.replace("/", "")
            )

            required_margin = qty * entry / LEVERAGE_MAP.get(normalized_symbol, 5)
            if required_margin > available_margin * 0.9:  # Буфер 90%
                log(
                    f"⚠️ Skipping {symbol} — insufficient margin (required: {required_margin:.2f}, available: {available_margin:.2f})",
                    level="WARNING",
                )
                send_telegram_message(f"⚠️ Insufficient margin for {symbol}", force=True)
                return None

            # Check notional requirement for opening a position
            notional = qty * entry
            markets = exchange.load_markets()
            api_symbol = symbol
            min_notional = (
                markets[api_symbol]["limits"]["amount"]["min"] * entry
                if api_symbol in markets
                else MIN_NOTIONAL_OPEN
            )
            if notional < min_notional:
                log(
                    f"⚠️ Notional too low for {symbol} — notional: {notional:.2f}, required: {min_notional:.2f}, skipping",
                    level="WARNING",
                )
                send_telegram_message(f"⚠️ Notional too low for {symbol}", force=True)
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
        send_telegram_message(f"❌ Error in process_symbol for {symbol}: {e}", force=True)
        return None
