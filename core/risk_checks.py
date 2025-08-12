#!/usr/bin/env python3
"""Risk management checks before position entry"""


async def check_margin_before_entry(
    order_manager,
    symbol: str,
    intended_margin_usdc: float,
    deposit: float = 400,
) -> tuple[bool, str]:
    """
    Check if we have enough margin for new position.

    Args:
        order_manager: OrderManager instance
        symbol: Trading symbol
        intended_margin_usdc: Required margin for new position
        deposit: Total deposit amount

    Returns:
        (allowed, reason) tuple
    """
    active_positions = order_manager.get_active_positions()
    used_margin = sum(float(p.get("margin", 0.0)) for p in active_positions)
    total = used_margin + float(intended_margin_usdc)

    # 50% max utilization for $400 deposit
    limit = deposit * 0.5

    if total > limit:
        return False, f"Margin usage {total:.2f} > limit {limit:.2f}"

    return True, "OK"


async def check_daily_drawdown(order_manager, max_dd_pct: float = 2.0) -> tuple[bool, str]:
    """
    Check if daily drawdown limit reached.

    Args:
        order_manager: OrderManager instance
        max_dd_pct: Maximum daily drawdown percentage

    Returns:
        (allowed, reason) tuple
    """
    # Check Stage F state if available
    if hasattr(order_manager, "risk_guard_f"):
        status = order_manager.risk_guard_f.status()
        daily_loss = status.get("daily_loss_pct", 0)
        if daily_loss >= max_dd_pct:
            return False, f"Daily loss {daily_loss:.2f}% >= limit {max_dd_pct}%"

    return True, "OK"
