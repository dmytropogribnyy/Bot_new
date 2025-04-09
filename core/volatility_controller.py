import time

import pandas as pd

from config import EXPORT_PATH
from utils_logging import log


def get_filter_relax_factor():
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
    relax = get_filter_relax_factor()

    atr_thres = max(base_filters["atr"] * relax, 0.0005)
    adx_thres = max(base_filters["adx"] * relax, 3)
    bb_thres = max(base_filters["bb"] * relax, 0.004)

    return {"atr": atr_thres, "adx": adx_thres, "bb": bb_thres, "relax_factor": relax}
