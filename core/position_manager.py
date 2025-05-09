# core/position_manager.py
"""
Position management module for BinanceBot
Controls position limits, size calculations, and validates new position requests
"""

# Import from project modules
from common.config_loader import get_max_positions
from core.risk_utils import calculate_position_value_limit
from utils_core import get_cached_balance, safe_call_retry
from utils_logging import log


def get_open_positions_count():
    """
    Get the current number of open positions
    Returns: int - Number of open positions
    """
    from core.exchange_init import exchange

    try:
        positions = safe_call_retry(exchange.fetch_positions)
        open_positions = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
        return len(open_positions)
    except Exception as e:
        log(f"Error in get_open_positions_count: {e}", level="ERROR")
        # Default to a safe value if we can't get actual count
        return get_max_positions()


def can_open_new_position(balance):
    """
    Limit simultaneous positions based on account size

    Args:
        balance (float): Current account balance in USDC

    Returns:
        bool: True if a new position can be opened, False otherwise
    """
    current_positions = get_open_positions_count()

    # Limit to 2 positions for micro-deposits (< 150 USDC)
    if balance < 150:
        max_positions = 2
    elif balance < 300:
        max_positions = 3
    else:
        max_positions = 4

    # Add log to track position limits
    log(f"Position check: {current_positions}/{max_positions} positions used. " + f"Balance: {balance:.2f} USDC", level="DEBUG")

    return current_positions < max_positions


def get_position_size(symbol):
    """
    Get the current position size for a specific symbol

    Args:
        symbol (str): Trading pair symbol

    Returns:
        float: Position size (positive for long, negative for short, 0 for no position)
    """
    from core.exchange_init import exchange

    try:
        position = safe_call_retry(exchange.fetch_position, symbol)
        if position:
            return float(position.get("positionAmt", 0))
        return 0
    except Exception as e:
        log(f"Error in get_position_size for {symbol}: {e}", level="ERROR")
        return 0


def can_increase_position(symbol, additional_qty):
    """
    Check if we can safely increase an existing position

    Args:
        symbol (str): Trading pair symbol
        additional_qty (float): Additional position size to add

    Returns:
        bool: True if position can be increased, False otherwise
    """
    from core.exchange_init import exchange

    try:
        # Get current balance and position
        balance = get_cached_balance()
        position = safe_call_retry(exchange.fetch_position, symbol)

        if not position or float(position.get("positionAmt", 0)) == 0:
            return False  # Can't increase a non-existent position

        # Calculate current and new position values
        current_value = abs(float(position.get("positionValue", 0)))
        current_price = float(position.get("entryPrice", 0))
        additional_value = additional_qty * current_price

        # Calculate maximum allowed position value using the correct function
        max_position_value = calculate_position_value_limit(balance)

        # Check if new total would exceed maximum allowed
        return (current_value + additional_value) <= max_position_value

    except Exception as e:
        log(f"Error in can_increase_position for {symbol}: {e}", level="ERROR")
        return False


def execute_position_increase(symbol, side, additional_qty):
    """
    Increase an existing position by adding to it

    Args:
        symbol (str): Trading pair symbol
        side (str): 'buy' or 'sell'
        additional_qty (float): Additional position size to add

    Returns:
        dict: Order result or None if failed
    """
    from core.exchange_init import exchange
    from utils_core import safe_call_retry

    try:
        order_type = "MARKET"
        side = side.upper()

        # Execute the additional order
        order = safe_call_retry(exchange.create_order, symbol=symbol, type=order_type, side=side, amount=additional_qty)

        log(f"{symbol} 📈 Position increased by {additional_qty} through {side} {order_type}", level="INFO")
        return order

    except Exception as e:
        log(f"Error in execute_position_increase for {symbol}: {e}", level="ERROR")
        return None


def execute_partial_close(symbol, side, reduction_qty):
    """
    Close part of an existing position

    Args:
        symbol (str): Trading pair symbol
        side (str): Original position side ('buy' or 'sell')
        reduction_qty (float): Position size to close

    Returns:
        dict: Order result or None if failed
    """
    from core.exchange_init import exchange
    from utils_core import safe_call_retry

    try:
        # For partial close, use the opposite side of the original position
        close_side = "SELL" if side.upper() == "BUY" else "BUY"
        order_type = "MARKET"

        # Execute the reduction order
        order = safe_call_retry(exchange.create_order, symbol=symbol, type=order_type, side=close_side, amount=reduction_qty)

        log(f"{symbol} 🔒 Partial position close: {reduction_qty} through {close_side} {order_type}", level="INFO")
        return order

    except Exception as e:
        log(f"Error in execute_partial_close for {symbol}: {e}", level="ERROR")
        return None
