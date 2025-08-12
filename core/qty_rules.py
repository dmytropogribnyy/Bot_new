#!/usr/bin/env python3
"""Dynamic quantity calculation rules"""

from core.precision import normalize


async def minimal_trade_qty(exchange, symbol: str, price: float) -> float:
    """
    Calculate minimum valid quantity from MIN_NOTIONAL and stepSize.

    Args:
        exchange: Exchange client instance
        symbol: Trading symbol
        price: Current price

    Returns:
        Minimum valid quantity
    """
    try:
        markets = await exchange.get_markets()
        market = markets.get(symbol, {})

        # Get minimum notional
        min_cost = market.get("limits", {}).get("cost", {}).get("min", 5.0)

        # Calculate rough quantity
        rough_qty = float(min_cost) / float(price)

        # Normalize to exchange precision
        _, qty_norm, _ = normalize(None, rough_qty, market, price, symbol)

        return qty_norm
    except Exception:
        # Fallback to safe minimum
        return 0.001
