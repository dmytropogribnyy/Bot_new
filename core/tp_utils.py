# tp_utils.py

from common.config_loader import (
    AUTO_TP_SL_ENABLED,
    FLAT_ADJUSTMENT,
    SL_PERCENT,
    TP1_PERCENT,
    TP1_SHARE,
    TP2_PERCENT,
    TP2_SHARE,
    TREND_ADJUSTMENT,
)


def calculate_tp_levels(entry_price: float, side: str, regime: str = None, score: float = 5):
    """
    Вычисляет цены TP1, TP2 и SL на основе цены входа, стороны и режима рынка.
    """
    tp1_pct = TP1_PERCENT
    tp2_pct = TP2_PERCENT
    sl_pct = SL_PERCENT

    if AUTO_TP_SL_ENABLED and regime:
        if regime == "flat":
            tp1_pct *= FLAT_ADJUSTMENT
            tp2_pct *= FLAT_ADJUSTMENT if tp2_pct else None
            sl_pct *= FLAT_ADJUSTMENT
        elif regime == "trend":
            tp2_pct *= TREND_ADJUSTMENT if tp2_pct else None
            sl_pct *= TREND_ADJUSTMENT

    if score == 3:
        tp1_pct *= 0.8
        tp2_pct = None
        sl_pct *= 0.8

    if side.lower() == "buy":
        tp1_price = entry_price * (1 + tp1_pct)
        tp2_price = entry_price * (1 + tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 - sl_pct)
    else:  # side == "sell"
        tp1_price = entry_price * (1 - tp1_pct)
        tp2_price = entry_price * (1 - tp2_pct) if tp2_pct else None
        sl_price = entry_price * (1 + sl_pct)

    qty_tp1 = TP1_SHARE
    qty_tp2 = TP2_SHARE if tp2_price else 0

    return (
        round(tp1_price, 4),
        round(tp2_price, 4) if tp2_price else None,
        round(sl_price, 4),
        qty_tp1,
        qty_tp2,
    )
