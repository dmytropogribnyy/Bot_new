

def ensure_perp_usdc_format(symbol: str) -> str:
    """Ensure ccxt perpetual USDC format like 'BTC/USDC:USDC' when possible."""
    if symbol.endswith(":USDC"):
        return symbol
    if symbol.endswith("/USDC"):
        return symbol + ":USDC"
    return symbol


def is_usdc_contract_market(market: dict) -> bool:
    """
    Return True if market represents an active USDC-settled contract (swap/future).
    Tolerates minor schema differences across ccxt versions.
    """
    if not isinstance(market, dict):
        return False
    is_active = market.get("active", True)
    if not is_active:
        return False
    is_contract = bool(market.get("contract", False))
    market_type = market.get("type")
    quote = market.get("quote")
    settle = market.get("settle")
    is_usdc = (quote == "USDC") or (settle == "USDC")
    return is_contract and is_usdc and (market_type in ("swap", "future", None))
