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


def check_entry_allowed(balance):
    """
    Проверяет, можно ли открыть новую позицию:
    - по количеству позиций
    - по capital utilization
    - по лимиту на количество входов в час
    """
    from datetime import datetime, timedelta

    from core.risk_utils import get_max_positions
    from core.trade_engine import trade_manager
    from utils_core import get_runtime_config, get_total_position_value
    from utils_logging import log

    config = get_runtime_config()
    max_positions = get_max_positions(balance)
    current_positions = trade_manager.count_active_positions()
    now = datetime.utcnow()

    # === Check: максимальное количество одновременных позиций
    if current_positions >= max_positions:
        log(f"[EntryCheck] ❌ Too many positions: {current_positions}/{max_positions}", level="INFO")
        return False, "position_limit_reached"

    # === Check: баланс должен быть положительным
    if balance <= 0:
        log("[EntryCheck] ❌ Cannot enter: balance is zero", level="WARNING")
        return False, "zero_balance"

    # === Check: capital utilization (с учётом текущих открытых)
    used_capital = get_total_position_value()
    max_cap_pct = config.get("max_capital_utilization_pct", 0.80)
    cap_utilization = used_capital / balance

    log(f"[EntryCheck] Capital usage = {cap_utilization:.2%}, limit = {max_cap_pct:.2%}", level="DEBUG")

    if cap_utilization > max_cap_pct:
        log(f"[EntryCheck] ❌ Capital usage too high: {cap_utilization:.2%}", level="INFO")
        return False, "capital_utilization_limit"

    # === Check: max_hourly_trade_limit (гибкий)
    hourly_limit = config.get("max_hourly_trade_limit", None)
    limit_mode = config.get("hourly_limit_check_mode", "active_only")

    if hourly_limit:
        recent_entries = 0
        one_hour_ago = now - timedelta(minutes=60)

        for trade in trade_manager.get_all_trades().values():
            start = trade.get("start_time")
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start)
                except Exception:
                    continue
            if not isinstance(start, datetime):
                continue

            is_open = not trade.get("tp1_hit") and not trade.get("sl_hit") and not trade.get("soft_exit_hit")
            if limit_mode == "active_only":
                if is_open:
                    recent_entries += 1
            else:
                if start >= one_hour_ago:
                    recent_entries += 1

        if recent_entries >= hourly_limit:
            log(f"[EntryCheck] ❌ Hourly trade limit reached: {recent_entries}/{hourly_limit}", level="INFO")
            return False, "hourly_limit_reached"

    log(f"[EntryCheck] ✅ Allowed to enter. Positions: {current_positions}/{max_positions}, Capital used: {cap_utilization:.2%}", level="DEBUG")
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
