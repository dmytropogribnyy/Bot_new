# order_utils.py
from common.config_loader import MIN_NOTIONAL_OPEN
from core.binance_api import convert_symbol, safe_call_retry
from core.exchange_init import exchange
from utils_logging import log


def calculate_order_quantity(entry_price: float, stop_price: float, balance: float, risk_percent: float) -> float:
    """
    Вычисляет количество контрактов для ордера.

    Формула: количество = (баланс * риск_percent) / (|entry_price - stop_price|)

    Включает проверку минимального нотиона биржи.
    """
    risk_amount = balance * risk_percent
    risk_per_contract = abs(entry_price - stop_price)
    qty = risk_amount / risk_per_contract if risk_per_contract > 0 else 0

    # Validate minimum notional
    notional = qty * entry_price
    if notional < MIN_NOTIONAL_OPEN:
        # Adjust quantity to meet minimum
        qty = MIN_NOTIONAL_OPEN / entry_price
        log(f"Adjusted quantity to {qty:.6f} to meet minimum notional ${MIN_NOTIONAL_OPEN}")

    return round(qty, 3)


def create_post_only_limit_order(symbol, side, amount, price):
    """
    Create a post-only limit order (to ensure maker fee).
    """
    api_symbol = convert_symbol(symbol)
    try:
        return safe_call_retry(exchange.create_order, api_symbol, "limit", side, amount, price, {"postOnly": True})
    except Exception as e:
        log(f"[Order] Failed to place post-only order for {symbol}: {e}", level="ERROR")
        return None
