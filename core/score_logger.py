# score_logger.py
import csv
import os
from datetime import datetime

from common.config_loader import DRY_RUN, get_adaptive_score_threshold
from utils_core import get_cached_balance
from utils_logging import log


def log_score_history(symbol, score):
    try:
        if DRY_RUN:
            return  # Don't log in DRY_RUN

        # Get account details for context
        balance = get_cached_balance()
        account_category = "Small" if balance < 150 else "Medium" if balance < 300 else "Standard"
        threshold = get_adaptive_score_threshold(balance)

        os.makedirs("data", exist_ok=True)
        filepath = "data/score_history.csv"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Check if file exists to determine if we need to write headers
        file_exists = os.path.isfile(filepath)

        with open(filepath, "a", newline="") as f:
            writer = csv.writer(f)

            # Write headers if file is new
            if not file_exists:
                writer.writerow(["Symbol", "Score", "Timestamp", "Balance", "Category", "Threshold"])

            # Write data with additional context
            writer.writerow([symbol, score, now_str, balance, account_category, threshold])

    except Exception as e:
        log(f"[ScoreHistory] Failed to log score for {symbol}: {e}", level="ERROR")


def log_score_components(symbol, score, breakdown):
    """
    Log detailed score component breakdown for analysis and optimization.

    Args:
        symbol: Trading pair symbol
        score: Final calculated score
        breakdown: Dictionary of component contributions
    """
    try:
        if DRY_RUN:
            return  # Don't log in DRY_RUN

        os.makedirs("data", exist_ok=True)
        filepath = "data/score_components.csv"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        file_exists = os.path.isfile(filepath)
        components = list(breakdown.keys())

        with open(filepath, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                headers = ["Symbol", "Score", "Timestamp"] + components
                writer.writerow(headers)
            row_data = [symbol, score, now_str] + [breakdown.get(k, 0) for k in components]
            writer.writerow(row_data)

    except Exception as e:
        log(f"[ScoreComponents] Failed to log components for {symbol}: {e}", level="ERROR")
