# volatility_controller.py
import time

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH
from utils_logging import log


def get_filter_relax_factor():
    if DRY_RUN:  # В DRY_RUN возвращаем дефолтное значение
        return 1.0
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        if df.empty:
            return 1.0  # По умолчанию

        trade_count = len(df)
        days = (time.time() - pd.to_datetime(df["Date"]).min().timestamp()) / (24 * 60 * 60)
        trades_per_day = trade_count / max(days, 1)

        # Линейное сглаживание: 0.7 → 1.1 при 0–7+ сделках в день
        relax = min(1.1, max(0.7, 0.7 + 0.05 * trades_per_day))
        return relax
    except Exception as e:
        log(f"[FilterAdaptation] Error calculating relax factor: {e}")
        return 1.0


def get_volatility_filters(symbol, base_filters):
    from common.config_loader import get_priority_small_balance_pairs
    from utils_core import get_cached_balance, get_runtime_config

    balance = get_cached_balance()
    config = get_runtime_config()
    relax = get_filter_relax_factor()
    runtime_relax = config.get("relax_factor", relax)

    filters = base_filters.copy()

    # Apply relax factor
    relax_multiplier = 1 - runtime_relax
    filters["atr"] *= relax_multiplier
    filters["adx"] *= relax_multiplier
    filters["bb"] *= relax_multiplier
    filters["relax_factor"] = runtime_relax

    # Special treatment for small balance accounts
    if balance < 300:
        if symbol in get_priority_small_balance_pairs():
            filters["atr"] *= 0.9
            filters["adx"] *= 0.9
            filters["bb"] *= 0.9
            log(f"⚙️ Priority pair {symbol} for small account – relaxed filters", level="DEBUG")
        else:
            filters["atr"] *= 1.1
            filters["adx"] *= 1.1
            filters["bb"] *= 1.1

    # 🔹 Dynamic min-thresholds based on market volatility (future-proof)
    avg_market_atr = config.get("market_volatility", 0.5)
    if avg_market_atr < 0.4:
        min_thresholds = {"atr": 0.0003, "adx": 4.0, "bb": 0.0015}
    elif avg_market_atr < 0.6:
        min_thresholds = {"atr": 0.0004, "adx": 5.0, "bb": 0.0020}
    else:
        min_thresholds = {"atr": 0.0005, "adx": 6.0, "bb": 0.0025}

    # Enforce minimum thresholds
    filters["atr"] = max(filters["atr"], min_thresholds["atr"])
    filters["adx"] = max(filters["adx"], min_thresholds["adx"])
    filters["bb"] = max(filters["bb"], min_thresholds["bb"])

    return filters
