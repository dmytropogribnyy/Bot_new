from config import MIN_NOTIONAL, SL_PERCENT
from core.strategy import fetch_data, should_enter_trade
from core.trade_engine import calculate_position_size, calculate_risk_amount, get_position_size
from utils_core import get_adaptive_risk_percent
from utils_logging import log


def process_symbol(symbol, balance, last_trade_times, lock):
    try:
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

        direction, score = result
        entry = df["close"].iloc[-1]
        stop = entry * (1 - SL_PERCENT) if direction == "buy" else entry * (1 + SL_PERCENT)
        risk_percent = get_adaptive_risk_percent(balance)
        risk = calculate_risk_amount(balance, risk_percent)
        qty = calculate_position_size(entry, stop, risk)

        if qty * entry < MIN_NOTIONAL:
            log(f"⚠️ Notional too low for {symbol} — skipping", level="WARNING")
            return None

        return {
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry": entry,
            "score": score,
        }

    except Exception as e:
        log(f"🔥 Error in process_symbol for {symbol}: {e}", level="ERROR")
        return None
