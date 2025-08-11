def ensure_perp_usdc_format(symbol: str) -> str:
    """Ensure ccxt perpetual USDC format like 'BTC/USDC:USDC' when possible."""
    if symbol.endswith(":USDC"):
        return symbol
    if symbol.endswith("/USDC"):
        return symbol + ":USDC"
    return symbol


def is_usdc_contract_market(market: dict, quote_coin: str | None = None) -> bool:
    """
    Return True if market represents an active contract (swap/future) for specified quote coin.
    If quote_coin is None, attempts to resolve dynamically from TradingConfig.
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
    q = quote_coin
    if not q:
        try:
            # Lazy import to avoid circulars
            from core.config import TradingConfig  # type: ignore

            q = TradingConfig.from_env().resolved_quote_coin
        except Exception:
            q = ""
    return is_contract and (quote == q or settle == q) and (market_type in ("swap", "future", None))


def to_binance_symbol(canonical: str) -> str:
    """'BTC/USDT:USDT' → 'BTCUSDT'"""
    base, rest = canonical.split("/")
    quote = rest.split(":")[0]
    return f"{base}{quote}"


def base_of(canonical: str) -> str:
    return canonical.split("/")[0]


def quote_of(canonical: str) -> str:
    return canonical.split("/")[1].split(":")[0]


def default_symbols(quote: str) -> list[str]:
    """Default symbols for specified quote currency"""
    majors = ["BTC", "ETH", "SOL", "BNB", "XRP"]
    q = (quote or "USDC").upper()
    return [f"{b}/{q}:{q}" for b in majors]


def normalize_symbol(symbol) -> str:
    """
    Normalize a symbol into BASE/QUOTE:QUOTE canonical form.
    Tolerates dict inputs with a 'symbol' key.
    """
    if isinstance(symbol, dict):
        symbol = symbol.get("symbol", "")
    if not isinstance(symbol, str) or not symbol:
        return ""
    s = symbol.upper().split(":")[0]
    s = s.replace("-", "/").replace(":", "/")
    if "/" not in s:
        return s
    base, quote = s.split("/", 1)
    return f"{base}/{quote}:{quote}"
