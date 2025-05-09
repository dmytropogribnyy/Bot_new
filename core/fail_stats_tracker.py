# core/fail_stats_tracker.py
import json
import os
from threading import Lock

FAIL_STATS_FILE = "data/fail_stats.json"
fail_stats_lock = Lock()


def record_failure_reason(symbol, reasons):
    """
    Increment counters for failure reasons by symbol.

    Args:
        symbol (str): Trading pair symbol
        reasons (list): List of failure reasons (strings)
    """
    if not reasons:
        return

    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)
            else:
                data = {}

            if symbol not in data:
                data[symbol] = {}

            for reason in reasons:
                data[symbol][reason] = data[symbol].get(reason, 0) + 1

            with open(FAIL_STATS_FILE, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            from utils_logging import log

            log(f"[FailStats] Error recording failure for {symbol}: {e}", level="ERROR")


def get_signal_failure_stats():
    """
    Retrieve aggregated statistics about signal failures from the tracking data.

    Returns:
        dict: Dictionary with aggregated failure statistics by symbol and reason
    """
    with fail_stats_lock:
        try:
            if os.path.exists(FAIL_STATS_FILE):
                with open(FAIL_STATS_FILE, "r") as f:
                    data = json.load(f)
                return data
            else:
                return {}
        except Exception as e:
            from utils_logging import log

            log(f"[FailStats] Error retrieving failure stats: {e}", level="ERROR")
            return {}
