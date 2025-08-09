import time

import requests

_open_interest_cache = {}
CACHE_TTL = 300  # 5 минут


def fetch_open_interest(symbol):
    """
    Fetch current open interest for a symbol from Binance USDC Futures.
    Symbol must be in format 'BTC/USDC'.
    """
    binance_symbol = symbol.replace("/", "").upper()  # BTC/USDC → BTCUSDC
    now = time.time()

    if symbol in _open_interest_cache:
        cached_value, last_time = _open_interest_cache[symbol]
        if now - last_time < CACHE_TTL:
            return cached_value

    try:
        response = requests.get(
            "https://fapi.binance.com/fapi/v1/openInterest", params={"symbol": binance_symbol}, timeout=5
        )
        if response.status_code != 200:
            return 0.0

        data = response.json()
        open_interest = float(data.get("openInterest", 0))
        _open_interest_cache[symbol] = (open_interest, now)
        return open_interest
    except Exception:
        return 0.0
