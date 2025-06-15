# order_utils.py
from core.binance_api import convert_symbol, safe_call_retry
from core.exchange_init import exchange
from utils_core import extract_symbol
from utils_logging import log


def calculate_order_quantity(entry_price: float, stop_price: float, balance: float, risk_percent: float, symbol: str) -> float:
    """
    Вычисляет количество контрактов с учётом риска и ограничения по капиталу и плечу.
    """
    from common.config_loader import MIN_NOTIONAL_OPEN
    from common.leverage_config import get_leverage_for_symbol
    from utils_logging import log

    risk_amount = balance * risk_percent
    risk_per_contract = abs(entry_price - stop_price)
    qty = risk_amount / risk_per_contract if risk_per_contract > 0 else 0

    # === Capital Utilization Cap
    leverage = get_leverage_for_symbol(symbol)
    max_notional = balance * leverage * 0.80
    max_qty = max_notional / entry_price

    if qty * entry_price > max_notional:
        log(f"[Risk] ⚠️ Adjusting qty to respect capital cap → {qty:.4f} → {max_qty:.4f}", level="WARNING")
        qty = max_qty

    # === Ensure meets min notional
    notional = qty * entry_price
    if notional < MIN_NOTIONAL_OPEN:
        qty = MIN_NOTIONAL_OPEN / entry_price
        log(f"⚠️ Adjusted qty to {qty:.6f} to meet min notional ${MIN_NOTIONAL_OPEN}", level="WARNING")

    return round(qty, 3)


def create_post_only_limit_order(symbol, side, amount, price):
    """
    Create a post-only limit order (to ensure maker fee).
    """
    symbol = extract_symbol(symbol)
    api_symbol = convert_symbol(symbol)
    try:
        return safe_call_retry(exchange.create_order, api_symbol, "limit", side, amount, price, {"postOnly": True, "reduceOnly": True})
    except Exception as e:
        log(f"[Order] Failed to place post-only order for {symbol}: {e}", level="ERROR")
        return None
