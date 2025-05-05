# volatility_controller.py
import time

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH  # ✅ добавили сюда
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
    from utils_core import get_cached_balance

    # Get account balance for adaptive filtering
    balance = get_cached_balance()

    # Get standard relaxation factor
    relax = get_filter_relax_factor()

    # For small accounts, apply different filtering strategy
    if balance < 150:
        # Check if this is a priority pair for small accounts
        from common.config_loader import PRIORITY_SMALL_BALANCE_PAIRS

        is_priority = symbol in PRIORITY_SMALL_BALANCE_PAIRS

        if is_priority:
            # More permissive for priority pairs on small accounts
            atr_thres = max(base_filters["atr"] * relax * 0.9, 0.0004)
            adx_thres = max(base_filters["adx"] * relax * 0.9, 5)
            bb_thres = max(base_filters["bb"] * relax * 0.9, 0.002)
            log(f"Priority pair {symbol} for small account - using relaxed filters")
        else:
            # More strict for non-priority pairs on small accounts
            atr_thres = max(base_filters["atr"] * relax * 1.1, 0.0006)
            adx_thres = max(base_filters["adx"] * relax * 1.1, 8)
            bb_thres = max(base_filters["bb"] * relax * 1.1, 0.0025)
    else:
        # Standard filtering for larger accounts
        atr_thres = max(base_filters["atr"] * relax, 0.0004)
        adx_thres = max(base_filters["adx"] * relax, 5)
        bb_thres = max(base_filters["bb"] * relax, 0.002)

    return {"atr": atr_thres, "adx": adx_thres, "bb": bb_thres, "relax_factor": relax}
