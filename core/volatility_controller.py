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
    from utils_core import get_cached_balance, get_runtime_config

    # Get account balance for adaptive filtering
    balance = get_cached_balance()

    # Get standard relaxation factor
    relax = get_filter_relax_factor()

    # Copy base filters
    filters = base_filters.copy()

    # Apply relax factor to thresholds using simple multiplier
    multiplier = 1 - relax  # relax=0.3 → 0.7 multiplier (30% more permissive)
    filters["atr"] *= multiplier
    filters["adx"] *= multiplier
    filters["bb"] *= multiplier

    # For small accounts, apply different filtering strategy
    if balance < 150:
        # Check if this is a priority pair for small accounts
        from common.config_loader import PRIORITY_SMALL_BALANCE_PAIRS

        is_priority = symbol in PRIORITY_SMALL_BALANCE_PAIRS

        if is_priority:
            # More permissive for priority pairs on small accounts
            filters["atr"] *= 0.9
            filters["adx"] *= 0.9
            filters["bb"] *= 0.9
            log(f"Priority pair {symbol} for small account - using relaxed filters")
        else:
            # More strict for non-priority pairs on small accounts
            filters["atr"] *= 1.1
            filters["adx"] *= 1.1
            filters["bb"] *= 1.1

    # Apply runtime relax factor if different
    runtime_relax = get_runtime_config().get("relax_factor", relax)
    if runtime_relax != relax:
        adjustment = runtime_relax / relax
        filters["atr"] = base_filters["atr"] * (1 - runtime_relax) * adjustment
        filters["adx"] = base_filters["adx"] * (1 - runtime_relax) * adjustment
        filters["bb"] = base_filters["bb"] * (1 - runtime_relax) * adjustment
        filters["relax_factor"] = runtime_relax

    # Ensure minimum thresholds (safety net)
    filters["atr"] = max(filters["atr"], 0.0004)
    filters["adx"] = max(filters["adx"], 5.0)
    filters["bb"] = max(filters["bb"], 0.002)

    return filters
