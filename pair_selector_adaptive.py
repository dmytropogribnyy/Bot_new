
from core.strategy import fetch_data_multiframe
from utils_logging import log

FILTER_TIERS = [
    {"atr": 0.006, "volume": 600},
    {"atr": 0.005, "volume": 500},
    {"atr": 0.004, "volume": 400},
    {"atr": 0.003, "volume": 300},
]

def get_market_volatility_index(base_symbol="BTC/USDC"):
    df = fetch_data_multiframe(base_symbol)
    if df is None or len(df) < 10:
        return None
    price = df["close"].iloc[-1]
    atr = df["atr"].iloc[-1]
    return round(atr / price, 4)

def select_active_symbols(valid_symbols):
    vix = get_market_volatility_index()
    if vix and vix < 0.004:
        FILTER_TIERS.insert(0, {"atr": 0.003, "volume": 300})
        log("[Volatility] Market quiet — inserting softer tier first", level="INFO")

    for tier in FILTER_TIERS:
        active_pairs = []
        for symbol in valid_symbols:
            df = fetch_data_multiframe(symbol)
            if df is None or len(df) < 10:
                continue
            price = df["close"].iloc[-1]
            atr = df["atr"].iloc[-1]
            volume = df["volume"].iloc[-1] * price
            atr_pct = atr / price

            if atr_pct >= tier["atr"] and volume >= tier["volume"]:
                active_pairs.append(symbol)

        log(f"[FilterTier] Using thresholds ATR>={tier['atr']*100:.2f}%, Volume>={tier['volume']}", level="INFO")

        if len(active_pairs) >= 10:  # MIN_DYNAMIC_PAIRS
            log(f"[FilterTier] Selected {len(active_pairs)} pairs at this tier", level="INFO")
            return active_pairs

    log("[FilterTier] Not enough pairs passed — using last tier fallback", level="WARNING")
    return active_pairs  # may be empty or minimal
