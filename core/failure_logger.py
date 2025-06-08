# core/failure_logger.py
import json
import os
from datetime import datetime
from threading import Lock

from constants import FAILURE_LOG_FILE
from utils_core import extract_symbol
from utils_logging import log

failure_log_lock = Lock()


def log_failure(symbol, reasons):
    """
    Log signal failure with structured reasons

    Args:
        symbol: Trading pair symbol
        reasons: List of failure reasons
    """
    symbol = extract_symbol(symbol)
    if not reasons:
        return

    entry = {"timestamp": datetime.utcnow().isoformat(), "symbol": symbol, "reasons": reasons}

    with failure_log_lock:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(FAILURE_LOG_FILE), exist_ok=True)

            # Load existing data
            try:
                with open(FAILURE_LOG_FILE, "r") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = []

            # Add new entry and limit size
            data.append(entry)
            data = data[-500:]  # Keep only the last 500 entries

            # Save back to file
            with open(FAILURE_LOG_FILE, "w") as f:
                json.dump(data, f, indent=2)

            log(f"Signal failure logged for {symbol}: {', '.join(reasons)}", level="DEBUG")
        except Exception as e:
            log(f"Error logging signal failure: {e}", level="ERROR")

    # 🔽 Add this line at the very end (outside try-except)
    from core.fail_stats_tracker import record_failure_reason

    record_failure_reason(symbol, reasons)
