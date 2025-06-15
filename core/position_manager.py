# core/position_manager.py
"""
Position management module for BinanceBot
Controls position limits, size calculations, and validates new position requests
"""

# Import from project modules
from core.risk_utils import get_max_positions
from utils_core import extract_symbol, safe_call_retry
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
    Проверяет, можно ли открыть новую позицию с учётом лимитов:
    - лимит на число одновременных позиций
    - лимит на задействованный капитал (≤85%)

    Args:
        balance (float): Текущий баланс аккаунта в USDC

    Returns:
        bool: True, если можно открыть позицию; False — если лимит превышен
    """
    from core.risk_utils import get_max_positions
    from utils_core import get_total_position_value
    from utils_logging import log

    current_positions = get_open_positions_count()
    max_positions = get_max_positions(balance)

    # Проверка лимита по количеству позиций
    if current_positions >= max_positions:
        log(f"[PositionLimit] ❌ {current_positions}/{max_positions} позиции уже заняты", level="INFO")
        return False

    # Проверка капитального использования
    position_value = get_total_position_value()
    cap_usage = position_value / balance if balance > 0 else 1

    # 🔍 Детализация капитального использования
    log(f"[DEBUG] Capital check → position_value={position_value:.2f}, balance={balance:.2f}, usage={cap_usage:.2%}", level="DEBUG")

    if cap_usage > 0.85:
        log(f"[CapitalLimit] ❌ Использовано {cap_usage:.2%} капитала (>85%)", level="INFO")
        return False

    log(f"[PositionCheck] ✅ {current_positions}/{max_positions} позиций. Capital used: {cap_usage:.2%}", level="DEBUG")
    return True


def check_entry_allowed(balance):
    """
    Проверяет, можно ли открыть новую позицию.
    Возвращает (True, None) если да,
             или (False, причина) если нет.
    """
    from core.risk_utils import get_max_positions
    from utils_core import get_total_position_value
    from utils_logging import log

    current_positions = get_open_positions_count()
    max_positions = get_max_positions(balance)

    if current_positions >= max_positions:
        log(f"[EntryCheck] ❌ Too many positions: {current_positions}/{max_positions}", level="INFO")
        return False, "position_limit_reached"

    position_value = get_total_position_value()
    cap_usage = position_value / balance if balance > 0 else 1

    # 🔍 Логируем детализацию капитала
    log(f"[DEBUG] Capital check → position_value={position_value:.2f}, balance={balance:.2f}, usage={cap_usage:.2%}", level="DEBUG")

    if cap_usage > 0.85:
        log(f"[EntryCheck] ❌ Capital usage too high: {cap_usage:.2%}", level="INFO")
        return False, "capital_utilization_limit"

    log(f"[EntryCheck] ✅ Allowed to enter. Positions: {current_positions}/{max_positions}, Capital used: {cap_usage:.2%}", level="DEBUG")
    return True, None


def can_increase_position(symbol, additional_qty):
    """
    Проверяет, можно ли безопасно увеличить существующую позицию.

    Args:
        symbol (str): Тикер
        additional_qty (float): Дополнительный объём

    Returns:
        bool: True если можно, False если превышает лимит или нет позиции
    """
    symbol = extract_symbol(symbol)
    from core.exchange_init import exchange
    from core.risk_utils import calculate_position_value_limit
    from utils_core import get_cached_balance, safe_call_retry
    from utils_logging import log

    try:
        balance = get_cached_balance()
        position = safe_call_retry(exchange.fetch_position, symbol)

        if not position or float(position.get("positionAmt", 0)) == 0:
            log(f"[Check] ❌ Нельзя увеличить — позиция по {symbol} не активна", level="DEBUG")
            return False

        current_value = abs(float(position.get("positionValue", 0)))
        current_price = float(position.get("entryPrice", 0))
        additional_value = additional_qty * current_price
        new_total = current_value + additional_value

        max_position_value = calculate_position_value_limit(balance)

        # 🔍 Логируем лимиты по позиции
        log(
            f"[DEBUG] Increase check for {symbol} → current_value={current_value:.2f}, " f"add={additional_value:.2f}, new_total={new_total:.2f}, max={max_position_value:.2f}", level="DEBUG"
        )

        if new_total > max_position_value:
            log(f"[Check] ❌ Превышен лимит позиции {symbol}: {new_total:.2f} > {max_position_value:.2f}", level="INFO")
            return False

        log(f"[Check] ✅ Можно увеличить позицию {symbol} на {additional_qty}", level="DEBUG")
        return True

    except Exception as e:
        log(f"Error in can_increase_position for {symbol}: {e}", level="ERROR")
        return False


def execute_position_increase(symbol, side, additional_qty):
    """
    Увеличивает существующую позицию.

    Args:
        symbol (str): Тикер
        side (str): 'BUY' или 'SELL'
        additional_qty (float): Объём добавления

    Returns:
        dict: Результат ордера или None при ошибке
    """
    symbol = extract_symbol(symbol)
    from core.exchange_init import exchange
    from utils_core import safe_call_retry
    from utils_logging import log

    try:
        order_type = "MARKET"
        side = side.upper()

        log(f"[DEBUG] Executing position increase: {symbol}, side={side}, qty={additional_qty}", level="DEBUG")

        order = safe_call_retry(exchange.create_order, symbol=symbol, type=order_type, side=side, amount=additional_qty)

        log(f"[Position] {symbol} 📈 Увеличена позиция на {additional_qty} через {side} {order_type}", level="INFO")
        log(f"[DEBUG] Order result: {order}", level="DEBUG")

        return order

    except Exception as e:
        log(f"Error in execute_position_increase for {symbol}: {e}", level="ERROR")
        return None


def execute_partial_close(symbol, side, reduction_qty):
    """
    Частично закрывает открытую позицию.

    Args:
        symbol (str): Тикер
        side (str): Исходное направление ('BUY' или 'SELL')
        reduction_qty (float): Объём закрытия

    Returns:
        dict: Результат ордера или None при ошибке
    """
    symbol = extract_symbol(symbol)
    from core.exchange_init import exchange
    from utils_core import safe_call_retry
    from utils_logging import log

    try:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"
        order_type = "MARKET"

        log(f"[DEBUG] Executing partial close: {symbol}, side={close_side}, qty={reduction_qty}", level="DEBUG")

        order = safe_call_retry(exchange.create_order, symbol=symbol, type=order_type, side=close_side, amount=reduction_qty)

        log(f"[Position] {symbol} 🔒 Частично закрыто: {reduction_qty} через {close_side} {order_type}", level="INFO")
        log(f"[DEBUG] Order result: {order}", level="DEBUG")

        return order

    except Exception as e:
        log(f"Error in execute_partial_close for {symbol}: {e}", level="ERROR")
        return None
