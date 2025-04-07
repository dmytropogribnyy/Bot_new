# score_heatmap.py

import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from telegram.telegram_utils import escape_markdown_v2, send_telegram_image
from utils_logging import log

SCORE_HISTORY_FILE = "data/score_history.csv"
OUTPUT_IMAGE_PATH = "data/score_heatmap.png"


def generate_score_heatmap(days=7):
    if not os.path.exists(SCORE_HISTORY_FILE):
        log("score_history.csv not found", level="WARNING")
        return

    try:
        df = pd.read_csv(SCORE_HISTORY_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["timestamp"] >= cutoff]

        df["date"] = df["timestamp"].dt.date
        df = df.groupby(["symbol", "date"])["score"].mean().unstack(fill_value=0)

        plt.figure(figsize=(12, 6))
        sns.heatmap(df, annot=False, cmap="YlGnBu", linewidths=0.1, cbar=True)
        plt.title(f"Score Heatmap — Last {days} Days")
        plt.xlabel("Date")
        plt.ylabel("Symbol")
        plt.tight_layout()

        os.makedirs("data", exist_ok=True)
        plt.savefig(OUTPUT_IMAGE_PATH)
        plt.close()

        send_telegram_image(
            OUTPUT_IMAGE_PATH, caption=escape_markdown_v2(f"📊 *Score Heatmap* (last {days} days)")
        )
        log("Score heatmap generated and sent to Telegram", level="INFO")

    except Exception as e:
        log(f"Error generating heatmap: {e}", level="ERROR")
