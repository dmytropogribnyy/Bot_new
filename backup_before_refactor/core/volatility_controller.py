# volatility_controller.py
import time

import pandas as pd

from config import DRY_RUN, EXPORT_PATH  # Добавляем импорт DRY_RUN
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
    relax = get_filter_relax_factor()

    # atr_thres = max(base_filters["atr"] * relax, 0.0005)
    # adx_thres = max(base_filters["adx"] * relax, 3)
    # bb_thres = max(base_filters["bb"] * relax, 0.004)

    # Временно снижено для soft real run — усиленная проходимость сигналов

    atr_thres = max(base_filters["atr"] * relax, 0.0002)
    adx_thres = max(base_filters["adx"] * relax, 1)
    bb_thres = max(base_filters["bb"] * relax, 0.0015)

    return {"atr": atr_thres, "adx": adx_thres, "bb": bb_thres, "relax_factor": relax}
