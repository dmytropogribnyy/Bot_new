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
    "exit_reason",
    "fail_reason",
    "signal_score",
]

# Глобальный in-memory кэш для защиты от дубликатов.
# Ресетится при перезапуске бота.
_recent_entries = set()
# Максимальный размер кэша, чтобы не расти бесконтрольно.
_MAX_CACHE_SIZE = 5000


def log_entry(trade: dict, status="SUCCESS"):
    """
    Логирует информацию о входе в сделку в CSV файл.
    Защищает от дублирующихся записей.
    """
    try:
        # Проверяем валидность данных
        if not trade.get("entry") or not trade.get("qty"):
            log(
                f"[entry_logger] Skipping invalid log: entry={trade.get('entry')}, qty={trade.get('qty')}, symbol={trade.get('symbol')}",
                level="WARNING",
            )
            return

        balance = get_cached_balance()
        account_category = "Small" if balance < 120 else "Medium" if balance < 300 else "Standard"

        symbol = extract_symbol(trade.get("symbol", ""))
        direction = trade.get("side", "").lower()
        entry_price = float(trade.get("entry", 0) or 0)
        qty = float(trade.get("qty", 0) or 0)
        commission = qty * entry_price * TAKER_FEE_RATE * 2  # вход + выход

        # TP1 price и доля
        tp_prices = trade.get("tp_prices", [])
        tp1_price = tp_prices[0] if isinstance(tp_prices, list) and len(tp_prices) >= 1 else 0.0

        tp1_share = 0.7  # fallback
        try:
            from utils_core import get_runtime_config

            config = get_runtime_config()
            step_tp_sizes = config.get("step_tp_sizes", [])
            if isinstance(step_tp_sizes, list) and len(step_tp_sizes) > 0:
                tp1_share = float(step_tp_sizes[0]) or 0.7
        except Exception as e:
            log(f"[entry_logger] Fallback tp1_share used due to: {e}", level="WARNING")

        expected_profit = 0.0
        if tp1_price and entry_price and qty:
            gross = (
                qty * tp1_share * (tp1_price - entry_price)
                if direction == "buy"
                else qty * tp1_share * (entry_price - tp1_price)
            )
            expected_profit = gross - commission

        if expected_profit == 0.0:
            log(f"[entry_logger] ⚠️ expected_profit=0.0 for {symbol} @ {entry_price}, tp1={tp1_price}", level="WARNING")

        # Дополнительные параметры
        pair_type = (trade.get("type") or trade.get("pair_type") or "unknown").lower()
        if pair_type not in ["fixed", "dynamic"]:
            pair_type = "unknown"

        priority_flag = str(trade.get("priority_pair", "No")).strip().capitalize()
        if priority_flag not in ["Yes", "No"]:
            priority_flag = "No"

        exit_reason = trade.get("exit_reason", "-")
        fail_reason = trade.get("fail_reason", "-")

        if status != "SUCCESS":
            log(f"[entry_logger] ❌ FAIL log for {symbol} → reason: {fail_reason}", level="WARNING")

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
            "fail_reason": fail_reason,
            "signal_score": round(float(trade.get("signal_score", 0.0)), 4),
        }

        # Защита от дубликатов
        entry_key = f"{symbol}_{direction}_{round(entry_price, 6)}_{qty}"
        if entry_key in _recent_entries:
            log(f"[entry_logger] Skipping duplicate entry: {entry_key}", level="DEBUG")
            return
        _recent_entries.add(entry_key)

        # Ограничение размера кэша
        if len(_recent_entries) > _MAX_CACHE_SIZE:
            _recent_entries.clear()

        # Запись в CSV
        write_header = not os.path.exists(ENTRY_LOG_PATH)
        os.makedirs(os.path.dirname(ENTRY_LOG_PATH), exist_ok=True)

        with open(ENTRY_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(entry_dict)

        log(f"[entry_logger] Logged entry for {symbol} @ {entry_price:.6f}, qty={qty}", level="DEBUG")

    except Exception as e:
        log(f"[entry_logger] Failed to write log: {e}", level="ERROR")
