# missed_signal_logger.py
import json
import os
from datetime import datetime

from constants import MISSED_SIGNALS_LOG_FILE
from utils_logging import log


def log_missed_signal(symbol, score, breakdown, reason=""):
    """
    Log missed trading signals for analysis.

    Args:
        symbol (str): Trading pair symbol
        score (float): Signal score
        breakdown (dict): Components breakdown
        reason (str): Reason for signal rejection
    """
    timestamp = datetime.utcnow().isoformat()
    log_entry = {"timestamp": timestamp, "symbol": symbol, "score": score, "breakdown": breakdown, "reason": reason}

    # Create directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Append to missed signals log file
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

        # Keep only the last 100 entries to manage file size
        data = data[-99:] + [log_entry]

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        log(f"{symbol} Logged missed signal: {reason}, score={score:.2f}", level="DEBUG")
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
    filepath = "data/missed_signals.json"
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        # Sort by timestamp (newest first) and limit
        sorted_data = sorted(data, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_data[:limit]
    except Exception as e:
        log(f"Error reading missed signals: {e}", level="ERROR")
        return []
