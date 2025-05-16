# htf_optimizer.py

import datetime
import shutil

import pandas as pd

from common.config_loader import CONFIG_FILE, USE_HTF_CONFIRMATION  # ✅ добавили сюда
from constants import TP_CSV
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log

BACKUP_FILE = "config_backup.py"

HTF_MIN_TRADES = 30
HTF_ADVANTAGE_THRESHOLD = 0.10


def analyze_htf_winrate():
    try:
        df = pd.read_csv(TP_CSV)
        if "HTF Confirmed" not in df.columns:
            log("HTF Confirmed column not found in tp_performance.csv", level="WARNING")
            send_telegram_message(escape_markdown_v2("⚠️ HTF Confirmed column not found in `tp_performance.csv`\nAuto-analysis skipped."))
            return

        htf_true = df[df["HTF Confirmed"]]
        htf_false = df[~df["HTF Confirmed"]]

        if len(htf_true) < HTF_MIN_TRADES or len(htf_false) < HTF_MIN_TRADES:
            log("Not enough data for HTF analysis", level="INFO")
            send_telegram_message(escape_markdown_v2(f"ℹ️ Not enough trades for HTF auto-analysis\nHTF: {len(htf_true)} | No HTF: {len(htf_false)}"))
            return

        wr_true = len(htf_true[htf_true["Result"].isin(["TP1", "TP2"])]) / len(htf_true)
        wr_false = len(htf_false[htf_false["Result"].isin(["TP1", "TP2"])]) / len(htf_false)

        diff = wr_true - wr_false

        report = [
            "🧠 *HTF Trend Auto-Analysis*",
            f"HTF Confirmed: {len(htf_true)} | Winrate: {wr_true:.2%}",
            f"No HTF: {len(htf_false)} | Winrate: {wr_false:.2%}",
            f"Δ Winrate: {diff:.2%}",
        ]

        if diff >= HTF_ADVANTAGE_THRESHOLD and not USE_HTF_CONFIRMATION:
            _toggle_htf_filter(True)
            report.append("✅ HTF filter *enabled* automatically (winrate advantage)")

        elif diff < -HTF_ADVANTAGE_THRESHOLD and USE_HTF_CONFIRMATION:
            _toggle_htf_filter(False)
            report.append("❌ HTF filter *disabled* automatically (underperformance)")

        else:
            report.append("ℹ️ No HTF setting changed")

        send_telegram_message(escape_markdown_v2("\n".join(report)))

    except Exception as e:
        log(f"HTF Optimizer error: {e}", level="ERROR")
        send_telegram_message(escape_markdown_v2(f"❌ HTF Optimizer failed: {e}"))


def _toggle_htf_filter(state: bool):
    try:
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.startswith("USE_HTF_CONFIRMATION"):
                new_lines.append(f"USE_HTF_CONFIRMATION = {str(state)}\n")
            else:
                new_lines.append(line)

        with open(CONFIG_FILE, "w") as f:
            f.writelines(new_lines)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        suffix = "on" if state else "off"
        shutil.copy(CONFIG_FILE, f"{BACKUP_FILE}.htf_{suffix}.{timestamp}")
        log(f"HTF filter set to {state} and config backed up", level="INFO")

    except Exception as e:
        log(f"Failed to toggle HTF filter: {e}", level="ERROR")
