# tp_optimizer_ml.py (патч с адаптивным порогом сделок)

import datetime
import shutil

import pandas as pd

from config import (
    TP_ML_MIN_TRADES_INITIAL,
    TP_ML_MIN_TRADES_STABLE,
    TP_ML_SWITCH_THRESHOLD,
)
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log

TP_CSV = "data/tp_performance.csv"
CONFIG_FILE = "config.py"
BACKUP_FILE = "config_backup.py"


def analyze_and_optimize_tp():
    try:
        df = pd.read_csv(TP_CSV)
        total_trades = len(df)
        if df.empty or total_trades < 5:
            log("Not enough trade data for ML TP optimization", level="WARNING")
            return

        min_trades_required = (
            TP_ML_MIN_TRADES_INITIAL
            if total_trades < TP_ML_SWITCH_THRESHOLD
            else TP_ML_MIN_TRADES_STABLE
        )

        report_lines = [
            "🤖 *TP Optimizer ML Report*",
            f"📈 Using min trades per symbol: {min_trades_required} (total trades: {total_trades})",
        ]

        pairs = df["Symbol"].unique()
        updated = False
        skipped_symbols = []

        for symbol in pairs:
            symbol_df = df[df["Symbol"] == symbol]

            if len(symbol_df) < min_trades_required:
                skipped_symbols.append(symbol)
                continue

            tp1_hits = symbol_df[symbol_df["Result"] == "TP1"]
            tp2_hits = symbol_df[symbol_df["Result"] == "TP2"]
            sl_hits = symbol_df[symbol_df["Result"] == "SL"]

            tp1_wr = len(tp1_hits) / len(symbol_df)
            tp2_wr = len(tp2_hits) / len(symbol_df)
            sl_wr = len(sl_hits) / len(symbol_df)

            avg_tp1 = tp1_hits["PnL (%)"].mean() if not tp1_hits.empty else 0
            avg_tp2 = tp2_hits["PnL (%)"].mean() if not tp2_hits.empty else 0
            avg_sl = sl_hits["PnL (%)"].mean() if not sl_hits.empty else 0

            best_tp1 = round(min(max(avg_tp1 / 100, 0.004), 0.01), 4)
            best_tp2 = round(min(max(avg_tp2 / 100, 0.01), 0.03), 4)

            report_lines.append(
                f"🔹 *{symbol}*\n"
                f"- TP1 winrate: {tp1_wr:.0%}, avg: {avg_tp1:.2f}% → Suggest: {best_tp1:.4f}\n"
                f"- TP2 winrate: {tp2_wr:.0%}, avg: {avg_tp2:.2f}% → Suggest: {best_tp2:.4f}\n"
                f"- SL rate: {sl_wr:.0%}, avg SL: {avg_sl:.2f}%"
            )

            updated = True
            _update_config(symbol, best_tp1, best_tp2)

        if skipped_symbols:
            report_lines.append("\n⏭️ Skipped (not enough data): " + ", ".join(skipped_symbols))

        if updated:
            _backup_config()
            send_telegram_message(escape_markdown_v2("\n\n".join(report_lines)))
        else:
            send_telegram_message(
                escape_markdown_v2("No symbols met the criteria for TP ML optimization.")
            )

    except Exception as e:
        log(f"TP Optimizer ML failed: {str(e)}", level="ERROR")
        send_telegram_message(escape_markdown_v2(f"❌ TP ML optimization failed:\n{e}"))


def _update_config(symbol, tp1, tp2):
    try:
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        for line in lines:
            if f'"{symbol}"' in line and "tp1" in line:
                new_line = f'    "{symbol}": {{"tp1": {tp1}, "tp2": {tp2}}},\n'
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f'    "{symbol}": {{"tp1": {tp1}, "tp2": {tp2}}},\n')

        with open(CONFIG_FILE, "w") as f:
            f.writelines(new_lines)

        log(f"TP config updated for {symbol}: TP1={tp1}, TP2={tp2}", level="INFO")
    except Exception as e:
        log(f"Failed to update config for {symbol}: {e}", level="ERROR")


def _backup_config():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    shutil.copy(CONFIG_FILE, f"{BACKUP_FILE}.{timestamp}")
    log("Config backed up after TP ML optimization", level="INFO")
