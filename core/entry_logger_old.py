# entry_logger.py
import csv
import os
from datetime import datetime

from common.config_loader import DRY_RUN, TAKER_FEE_RATE
from constants import ENTRY_LOG_PATH
from utils_logging import log, log_dry_entry

FIELDNAMES = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "score",
    "notional",
    "mode",
    "status",
    "account_balance",  # Added for small account context
    "commission",  # Added for fee tracking
    "expected_profit",  # Added for absolute profit tracking
    "priority_pair",  # Added to track priority pairs
    "account_category",  # Added to categorize account size
]


def log_entry(trade: dict, status="SUCCESS", mode="DRY_RUN"):
    if DRY_RUN:
        log_dry_entry(trade)
        return

    # Get account balance
    from utils_core import get_cached_balance, normalize_symbol

    balance = get_cached_balance()

    # Determine account category - three-tier structure
    account_category = "Small" if balance < 120 else "Medium" if balance < 300 else "Standard"

    # Calculate commission
    entry_price = trade.get("entry", 0)
    qty = trade.get("qty", 0)
    commission = qty * entry_price * TAKER_FEE_RATE * 2  # Entry and exit

    # Check if this is a priority pair for small accounts
    from common.config_loader import PRIORITY_SMALL_BALANCE_PAIRS

    symbol = normalize_symbol(trade.get("symbol", ""))
    is_priority = "Yes" if symbol in PRIORITY_SMALL_BALANCE_PAIRS else "No"

    # Calculate expected profit (simple approximation)
    direction = trade.get("direction", "")
    tp1_price = trade.get("tp1", 0)
    tp1_share = 0.7  # Default TP1 share

    if tp1_price and entry_price:
        if direction.lower() == "buy":
            profit = qty * tp1_share * (tp1_price - entry_price)
        else:
            profit = qty * tp1_share * (entry_price - tp1_price)
        expected_profit = profit - commission
    else:
        expected_profit = 0

    os.makedirs(os.path.dirname(ENTRY_LOG_PATH), exist_ok=True)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "direction": direction,
        "entry_price": round(entry_price, 6),
        "score": trade.get("score"),
        "notional": round(entry_price * qty, 2),
        "mode": mode,
        "status": status,
        "account_balance": round(balance, 2),
        "commission": round(commission, 6),
        "expected_profit": round(expected_profit, 6),
        "priority_pair": is_priority,
        "account_category": account_category,
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
