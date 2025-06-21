import csv
import os
from datetime import datetime

from utils_logging import log

TP_SL_LOG_FILE = "data/tp_sl_debug.csv"


def log_tp_sl_event(symbol, level, qty, price, status, reason="-"):
    """
    Логирует событие TP/SL в tp_sl_debug.csv:
    - symbol: торговая пара (например, WIF/USDC)
    - level: TP1, TP2, TP3, SL, SKIPPED, ALL
    - qty: объём ордера
    - price: цена выставления
    - status: success, failure, skipped
    - reason: причина (qty_too_small, order_rejected, sl_too_close и т.п.)
    """
    os.makedirs("data", exist_ok=True)
    is_new_file = not os.path.exists(TP_SL_LOG_FILE)

    row = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "level": level,
        "qty": round(qty or 0, 8),
        "price": round(price or 0, 8),
        "status": status,
        "reason": reason,
    }

    try:
        with open(TP_SL_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if is_new_file:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        log(f"[TP/SL Logger] Failed to log TP/SL event: {e}", level="ERROR")
