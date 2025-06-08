# entry_logger.py

import csv
import os
from datetime import datetime

from common.config_loader import DRY_RUN, TAKER_FEE_RATE
from constants import ENTRY_LOG_PATH
from utils_core import extract_symbol
from utils_logging import log, log_dry_entry

FIELDNAMES = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "notional",
    "type",  # <-- Новое поле вместо "score"
    "mode",
    "status",
    "account_balance",
    "commission",
    "expected_profit",
    "priority_pair",
    "account_category",
]


def log_entry(trade: dict, status="SUCCESS", mode="DRY_RUN"):
    if DRY_RUN:
        # Если DRY_RUN, то просто выводим лог в консоль (log_dry_entry)
        log_dry_entry(trade)
        return

    # Получаем баланс (для расчёта account_category)
    from utils_core import get_cached_balance

    balance = get_cached_balance()

    # Трёхуровневая категоризация аккаунта
    if balance < 120:
        account_category = "Small"
    elif balance < 300:
        account_category = "Medium"
    else:
        account_category = "Standard"

    # Рассчитываем примерную комиссию (entry + exit)
    entry_price = trade.get("entry", 0)
    qty = trade.get("qty", 0)
    commission = qty * entry_price * TAKER_FEE_RATE * 2

    symbol = extract_symbol(trade.get("symbol", ""))

    # Пытаемся рассчитать ожидаемую прибыль (примерно).
    direction = trade.get("direction", "")
    tp1_price = trade.get("tp1", 0)
    tp1_share = 0.7  # 70% позиции на TP1
    if tp1_price and entry_price:
        if direction.lower() == "buy":
            gross_profit = qty * tp1_share * (tp1_price - entry_price)
        else:
            gross_profit = qty * tp1_share * (entry_price - tp1_price)
        expected_profit = gross_profit - commission
    else:
        expected_profit = 0

    # Новое поле type (fixed/dynamic/unknown)
    pair_type = trade.get("type", "unknown")

    # Готовим словарь для записи в CSV
    entry_dict = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "direction": direction,
        "entry_price": round(entry_price, 6),
        "notional": round(entry_price * qty, 2),
        "type": pair_type,
        "mode": mode,
        "status": status,
        "account_balance": round(balance, 2),
        "commission": round(commission, 6),
        "expected_profit": round(expected_profit, 6),
        "priority_pair": trade.get("priority_pair", "No"),
        "account_category": account_category,
    }

    # Если файла ещё нет, пишем заголовок
    write_header = not os.path.exists(ENTRY_LOG_PATH)

    try:
        os.makedirs(os.path.dirname(ENTRY_LOG_PATH), exist_ok=True)
        with open(ENTRY_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(entry_dict)
    except Exception as e:
        log(f"[entry_logger] Failed to write log: {e}", level="ERROR")
