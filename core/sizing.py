#!/usr/bin/env python3
"""Position sizing from risk calculation"""

from dataclasses import dataclass


@dataclass
class SizingResult:
    notional: float
    margin: float
    qty: float
    risk_usdc: float
    leverage: int


async def calculate_position_from_risk(
    exchange,
    symbol: str,
    price: float,
    risk_usdc: float,
    sl_percent: float,
    leverage: int = 5,
) -> SizingResult:
    """
    Calculate position size from dollar risk.

    Args:
        exchange: Exchange client instance
        symbol: Trading symbol
        price: Current price
        risk_usdc: Dollar risk per trade
        sl_percent: Stop loss percentage
        leverage: Trading leverage

    Returns:
        SizingResult with calculated values
    """
    sl_distance = sl_percent / 100.0
    notional = risk_usdc / sl_distance  # Notional position size
    margin = notional / leverage  # Required margin
    qty = notional / price  # Number of contracts

    return SizingResult(
        notional=notional,
        margin=margin,
        qty=qty,
        risk_usdc=risk_usdc,
        leverage=leverage,
    )
