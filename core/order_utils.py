# order_utils.py
from core.binance_api import convert_symbol, safe_call_retry
from core.exchange_init import exchange
from utils_core import extract_symbol
from utils_logging import log


def calculate_order_quantity(
    entry_price: float, stop_price: float, balance: float, risk_percent: float, symbol: str
) -> float:
    """
    Вычисляет количество контрактов с учётом риска, капитализации, min notional и min trade qty.
    """
    from common.config_loader import MIN_NOTIONAL_OPEN, get_runtime_config
    from common.leverage_config import get_leverage_for_symbol

    from utils_core import round_step_size
    from utils_logging import log

    cfg = get_runtime_config()
    min_qty = cfg.get("min_trade_qty", 0.001)
    capital_pct = cfg.get("max_capital_utilization_pct", 0.7)

    risk_amount = balance * risk_percent
    risk_per_contract = abs(entry_price - stop_price)

    if risk_per_contract <= 0:
        log(f"[Risk] ❌ Invalid stop distance for {symbol}", level="ERROR")
        return 0.0

    qty = risk_amount / risk_per_contract

    # === Capital Utilization Cap
    leverage = get_leverage_for_symbol(symbol)
    max_notional = balance * leverage * capital_pct
    max_qty = max_notional / entry_price

    if qty * entry_price > max_notional:
        log(f"[Risk] ⚠️ Adjusting qty to respect capital cap → {qty:.4f} → {max_qty:.4f}", level="WARNING")
        qty = max_qty

    # === Ensure meets min notional
    notional = qty * entry_price
    if notional < MIN_NOTIONAL_OPEN:
        qty = MIN_NOTIONAL_OPEN / entry_price
        log(f"⚠️ Adjusted qty to {qty:.6f} to meet min notional ${MIN_NOTIONAL_OPEN}", level="WARNING")

    # === Округление и проверка min_trade_qty
    qty = round_step_size(symbol, qty)

    if qty < min_qty:
        fallback_qty = cfg.get("fallback_order_qty", 0.01)
        if fallback_qty >= min_qty:
            log(f"[Risk] qty={qty:.6f} < min_trade_qty → using fallback qty={fallback_qty}", level="WARNING")
            qty = round_step_size(symbol, fallback_qty)
        else:
            log(f"[Risk] ❌ qty={qty:.6f} < min_trade_qty={min_qty} → blocked", level="WARNING")
            return 0.0

    return qty


def create_post_only_limit_order(symbol, side, amount, price):
    """
    Create a post-only limit order (to ensure maker fee).
    """
    symbol = extract_symbol(symbol)
    api_symbol = convert_symbol(symbol)
    try:
        return safe_call_retry(
            exchange.create_order, api_symbol, "limit", side, amount, price, {"postOnly": True, "reduceOnly": True}
        )
    except Exception as e:
        log(f"[Order] Failed to place post-only order for {symbol}: {e}", level="ERROR")
        return None
