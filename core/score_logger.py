# score_logger.py
import csv
import os
from datetime import datetime

from utils_logging import log


def log_score_history(symbol, score):
    # Move import inside the function
    from config import DRY_RUN

    try:
        if DRY_RUN:
            return  # Не логируем в DRY_RUN

        os.makedirs("data", exist_ok=True)
        filepath = "data/score_history.csv"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(filepath, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([symbol, score, now_str])
    except Exception as e:
        log(f"[ScoreHistory] Failed to log score for {symbol}: {e}", level="ERROR")
