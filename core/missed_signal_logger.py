# missed_signal_logger.py

import json
import os
from datetime import datetime

from constants import MISSED_SIGNALS_LOG_FILE
from utils_core import extract_symbol
from utils_logging import log


def log_missed_signal(symbol, breakdown, reason=""):
    """
    Log missed trading signals for analysis (without score).

    Args:
        symbol (str): Trading pair symbol
        breakdown (dict): Components breakdown
        reason (str): Reason for signal rejection
    """
    symbol = extract_symbol(symbol)
    timestamp = datetime.utcnow().isoformat()

    # Подсчёт силы сигнала
    primary_sum = sum(
        [
            breakdown.get("MACD", 0),
            breakdown.get("EMA_CROSS", 0),
            breakdown.get("RSI", 0),
        ]
    )
    secondary_sum = sum(
        [
            breakdown.get("Volume", 0),
            breakdown.get("PriceAction", 0),
            breakdown.get("HTF", 0),
        ]
    )

    log_entry = {
        "timestamp": timestamp,
        "symbol": symbol,
        "reason": reason,
        "atr_pct": round(breakdown.get("atr_percent", 0), 5),
        "volume": round(breakdown.get("volume", 0), 1),
        "rsi": round(breakdown.get("rsi", 0), 2),
        "risk_factor": round(breakdown.get("risk_factor", 0), 3),
        "entry_notional": round(breakdown.get("entry_notional", 0), 2),
        "passes_1plus1": breakdown.get("passes_1plus1", False),
        "primary_sum": primary_sum,
        "secondary_sum": secondary_sum,
        "components": breakdown,
    }

    os.makedirs("data", exist_ok=True)
    filepath = MISSED_SIGNALS_LOG_FILE

    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        data = data[-99:] + [log_entry]

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        log(f"{symbol} Logged missed signal: {reason}", level="DEBUG")
    except Exception as e:
        log(f"Error logging missed signal: {e}", level="ERROR")


def get_recent_missed_signals(limit=10):
    """
    Get the most recent missed signals.

    Args:
        limit (int): Maximum number of signals to return

    Returns:
        list: Recent missed signals
    """
    from constants import MISSED_SIGNALS_LOG_FILE

    filepath = MISSED_SIGNALS_LOG_FILE
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        sorted_data = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_data[:limit]
    except Exception as e:
        log(f"Error reading missed signals: {e}", level="ERROR")
        return []
