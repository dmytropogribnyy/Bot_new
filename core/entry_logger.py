import csv
import os
from datetime import datetime

from common.config_loader import TAKER_FEE_RATE
from constants import ENTRY_LOG_PATH
from utils_core import extract_symbol, get_cached_balance
from utils_logging import log

FIELDNAMES = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "notional",
    "type",
    "mode",
    "status",
    "account_balance",
    "commission",
    "expected_profit",
    "priority_pair",
    "account_category",
    "exit_reason",  # ✅ Новое поле
]


def log_entry(trade: dict, status="SUCCESS"):
    try:
        if not trade.get("entry") or not trade.get("qty"):
            log(f"[entry_logger] Skipping invalid log: entry={trade.get('entry')}, qty={trade.get('qty')}, symbol={trade.get('symbol')}", level="WARNING")
            return

        balance = get_cached_balance()
        account_category = "Small" if balance < 120 else "Medium" if balance < 300 else "Standard"

        symbol = extract_symbol(trade.get("symbol", ""))
        direction = trade.get("direction", "").lower()
        entry_price = float(trade.get("entry", 0) or 0)
        qty = float(trade.get("qty", 0) or 0)

        commission = qty * entry_price * TAKER_FEE_RATE * 2

        tp1_price = float(trade.get("tp1", 0) or 0)
        tp1_share = 0.7
        if tp1_price and entry_price:
            gross_profit = qty * tp1_share * (tp1_price - entry_price) if direction == "buy" else qty * tp1_share * (entry_price - tp1_price)
            expected_profit = gross_profit - commission
        else:
            expected_profit = 0.0

        pair_type = (trade.get("type") or trade.get("pair_type") or "unknown").lower()
        if pair_type not in ["fixed", "dynamic"]:
            pair_type = "unknown"

        priority_flag = str(trade.get("priority_pair", "No")).strip().capitalize()
        if priority_flag not in ["Yes", "No"]:
            priority_flag = "No"

        exit_reason = trade.get("exit_reason", "-")

        entry_dict = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "direction": direction.upper(),
            "entry_price": round(entry_price, 6),
            "notional": round(entry_price * qty, 2),
            "type": pair_type,
            "mode": "REAL_RUN",
            "status": status,
            "account_balance": round(balance, 2),
            "commission": round(commission, 6),
            "expected_profit": round(expected_profit, 6),
            "priority_pair": priority_flag,
            "account_category": account_category,
            "exit_reason": exit_reason,
        }

        write_header = not os.path.exists(ENTRY_LOG_PATH)
        os.makedirs(os.path.dirname(ENTRY_LOG_PATH), exist_ok=True)

        with open(ENTRY_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(entry_dict)

    except Exception as e:
        log(f"[entry_logger] Failed to write log: {e}", level="ERROR")
