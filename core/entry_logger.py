# entry_logger.py
import csv
import os
from datetime import datetime

from common.config_loader import DRY_RUN  # ✅ добавили сюда
from utils_logging import log, log_dry_entry

ENTRY_LOG_PATH = "data/entry_log.csv"

FIELDNAMES = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "score",
    "notional",
    "mode",
    "status",
]


def log_entry(trade: dict, status="SUCCESS", mode="DRY_RUN"):
    if DRY_RUN:
        log_dry_entry(trade)
        return

    os.makedirs(os.path.dirname(ENTRY_LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": trade.get("symbol"),
        "direction": trade.get("direction"),
        "entry_price": round(trade.get("entry", 0), 6),
        "score": trade.get("score"),
        "notional": round(trade.get("entry", 0) * trade.get("qty", 0), 2),
        "mode": mode,
        "status": status,
    }
    write_header = not os.path.exists(ENTRY_LOG_PATH)
    try:
        with open(ENTRY_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(entry)
    except Exception as e:
        log(f"[entry_logger] Failed to write log: {e}", level="ERROR")
