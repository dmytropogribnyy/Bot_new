import logging
import math

logger = logging.getLogger(__name__)


class PrecisionError(ValueError):
    """Raised when price/quantity/notional constraints are violated."""


def _to_float(value: str | float | int | None) -> float | None:
    """Best-effort conversion to float; returns None on missing/zero/invalid.

    Treats non-positive values as None for filter semantics (e.g., "0" → None).
    """
    if value is None:
        return None
    try:
        f = float(value)
        return f if f > 0 else None
    except Exception:
        return None


def round_to_step(x: float, step: float) -> float:
    """Round down to the nearest multiple of step using floor semantics.

    Example: round_to_step(1.237, 0.001) -> 1.237; round_to_step(1.2374, 0.001) -> 1.237
    """
    if step <= 0:
        return x
    return math.floor(x / step) * step


def extract_binance_filters(market: dict) -> dict:
    """Extract Binance-like filters from market['info']['filters'].

    Returns a dict with optional floats (or None) for:
      - tick, minPrice, maxPrice (PRICE_FILTER)
      - step, minQty, maxQty (LOT_SIZE or MARKET_LOT_SIZE)
      - minNotional (MIN_NOTIONAL or NOTIONAL)

    If filters are absent, all fields are None.
    """
    result = {
        "tick": None,
        "minPrice": None,
        "maxPrice": None,
        "step": None,
        "minQty": None,
        "maxQty": None,
        "minNotional": None,
    }

    try:
        filters = (market or {}).get("info", {}).get("filters", []) or []
    except Exception:
        filters = []

    # First pass: PRICE_FILTER, LOT_SIZE, MARKET_LOT_SIZE, MIN_NOTIONAL/NOTIONAL
    price_filter = next((f for f in filters if f.get("filterType") == "PRICE_FILTER"), None)
    lot_size = next((f for f in filters if f.get("filterType") == "LOT_SIZE"), None)
    market_lot_size = next((f for f in filters if f.get("filterType") == "MARKET_LOT_SIZE"), None)
    min_notional = next((f for f in filters if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL")), None)

    if price_filter:
        result["tick"] = _to_float(price_filter.get("tickSize"))
        result["minPrice"] = _to_float(price_filter.get("minPrice"))
        result["maxPrice"] = _to_float(price_filter.get("maxPrice"))

    # Prefer LOT_SIZE; fall back to MARKET_LOT_SIZE; merge per-field if one missing
    for source in (lot_size, market_lot_size):
        if not source:
            continue
        if result["step"] is None:
            result["step"] = _to_float(source.get("stepSize"))
        if result["minQty"] is None:
            result["minQty"] = _to_float(source.get("minQty"))
        if result["maxQty"] is None:
            result["maxQty"] = _to_float(source.get("maxQty"))

    if min_notional:
        # Some schemas use 'minNotional' or 'notional'
        result["minNotional"] = _to_float(min_notional.get("minNotional", min_notional.get("notional")))

    return result


def fallback_from_precision(market: dict) -> tuple[float | None, float | None]:
    """Fallback tick/step from market['precision'] digit counts.

    tick = 10 ** (-precision['price']) if present
    step = 10 ** (-precision['amount']) if present
    """
    precision = (market or {}).get("precision", {}) or {}
    tick: float | None = None
    step: float | None = None
    try:
        if "price" in precision and precision["price"] is not None:
            tick = 10 ** (-(int(precision["price"])))
    except Exception:
        tick = None
    try:
        if "amount" in precision and precision["amount"] is not None:
            step = 10 ** (-(int(precision["amount"])))
    except Exception:
        step = None
    return tick, step


def _extract_min_cost_limit(market: dict) -> float | None:
    try:
        limits = (market or {}).get("limits", {}) or {}
        cost = limits.get("cost", {}) or {}
        return _to_float(cost.get("min"))
    except Exception:
        return None


def normalize(
    price: float | None,
    qty: float,
    market: dict,
    current_price: float | None = None,
    symbol: str | None = None,
    logger: logging.Logger | None = None,
) -> tuple[float | None, float, float | None]:
    """Normalize price and quantity according to exchange filters and validate notional.

    Returns (price_norm, qty_norm, minNotional).

    Raises PrecisionError on violations or missing current price for market orders.
    """
    log = logger or globals().get("logger", logging.getLogger(__name__))

    filters = extract_binance_filters(market)
    tick = filters.get("tick")
    step = filters.get("step")
    min_price = filters.get("minPrice")
    max_price = filters.get("maxPrice")
    min_qty = filters.get("minQty")
    max_qty = filters.get("maxQty")
    min_notional = filters.get("minNotional")

    # Fallback from precision if missing
    if tick is None or step is None:
        fb_tick, fb_step = fallback_from_precision(market)
        if tick is None:
            tick = fb_tick
        if step is None:
            step = fb_step

    # Input validation
    if qty is None or qty <= 0:
        raise PrecisionError("qty must be > 0")
    if price is not None and price <= 0:
        raise PrecisionError("price must be > 0 when provided")

    # Normalization (floor to step)
    price_norm = round_to_step(price, tick) if (price is not None and tick is not None) else price
    qty_norm = round_to_step(qty, step) if (step is not None) else qty

    # Determine effective price
    effective_price = price_norm if price_norm is not None else current_price
    if effective_price is None:
        raise PrecisionError("current_price required for market order")

    # Boundary checks
    if min_price is not None and price_norm is not None and price_norm < min_price:
        raise PrecisionError("price below minPrice")
    if max_price is not None and price_norm is not None and price_norm > max_price:
        raise PrecisionError("price above maxPrice")
    if min_qty is not None and qty_norm < min_qty:
        raise PrecisionError("qty below minQty")
    if max_qty is not None and qty_norm > max_qty:
        raise PrecisionError("qty above maxQty")

    # Notional checks
    notional = float(effective_price) * float(qty_norm)
    if min_notional is not None and notional < min_notional:
        raise PrecisionError("Notional < MIN_NOTIONAL")
    else:
        limit_min_cost = _extract_min_cost_limit(market)
        if limit_min_cost is not None and notional < limit_min_cost:
            raise PrecisionError("Notional < MIN_NOTIONAL")

    try:
        log.debug(
            f"[PRECISION] {symbol or ''}: qty {qty}→{qty_norm}, price {price}→{price_norm}, "
            f"notional={notional}, minNotional={min_notional}"
        )
    except Exception:
        pass

    return price_norm, qty_norm, min_notional
