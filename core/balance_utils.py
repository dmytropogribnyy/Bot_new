"""Balance utilities for unified access"""


def free(balance: dict, code: str) -> float:
    """Get free balance for currency code"""
    b = balance or {}
    c = (code or "").upper()

    # Handle both {"USDT": {...}} and {"total": {"USDT": {...}}}
    if "total" in b and isinstance(b["total"], dict):
        d = b["total"].get(c, {})
    else:
        d = b.get(c, {})

    try:
        return float(d.get("free", 0) or 0)
    except Exception:
        # Tolerate balances where value might be nested or typed oddly
        try:
            return float(d or 0)
        except Exception:
            return 0.0
