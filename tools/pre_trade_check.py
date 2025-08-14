#!/usr/bin/env python3
"""Pre-trade validation filters"""


async def check_volume(exchange, symbol: str, size_usdc: float, mult: float = 100.0) -> bool:
    """Check if 24h volume is sufficient"""
    try:
        ticker = await exchange.get_ticker(symbol)
        qv = float(ticker.get("quoteVolume", 0) or 0)
        return qv >= size_usdc * mult
    except Exception:
        return False


async def check_spread(exchange, symbol: str, max_pct: float = 0.1) -> bool:
    """Check bid-ask spread"""
    try:
        ticker = await exchange.get_ticker(symbol)
        bid = float(ticker.get("bid", 0) or 0)
        ask = float(ticker.get("ask", 0) or 0)

        if not bid or not ask:
            return False

        # Use midprice-based spread percent
        mid = (ask + bid) / 2.0
        if mid <= 0:
            return False
        spread = abs(ask - bid) / mid * 100.0
        return spread <= max_pct
    except Exception:
        return False


async def can_enter_position(
    order_manager,
    symbol: str,
    planned_margin_usdc: float,
) -> tuple[bool, dict]:
    """
    Run all pre-trade checks.

    Returns:
        (allowed, check_details) tuple
    """
    exchange = order_manager.exchange
    checks: dict[str, bool] = {}

    # Volume check
    checks["volume"] = await check_volume(exchange, symbol, planned_margin_usdc)

    # Spread check (configurable, allow disabling on testnet)
    try:
        max_spread = float(getattr(order_manager.config, "max_spread_pct", 0.20))
    except Exception:
        max_spread = 0.20
    # Allow disabling on testnet
    if getattr(order_manager.config, "testnet", False) and getattr(
        order_manager.config, "disable_spread_filter_testnet", True
    ):
        checks["spread"] = True
    else:
        checks["spread"] = await check_spread(exchange, symbol, max_spread)

    # Position limit check
    max_positions = getattr(order_manager.config, "max_concurrent_positions", 2)
    checks["positions"] = order_manager.get_position_count() < max_positions

    # Daily drawdown check
    if hasattr(order_manager, "risk_guard_f"):
        can_open, _ = order_manager.risk_guard_f.can_open_new_position()
        checks["daily_dd"] = can_open
    else:
        checks["daily_dd"] = True

    return all(checks.values()), checks
