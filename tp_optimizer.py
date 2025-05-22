import json
import os
import re

import pandas as pd

from common.config_loader import CONFIG_FILE, EXPORT_PATH, TP1_PERCENT, TP2_PERCENT
from constants import BACKUP_PATH, STATUS_PATH
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
from utils_logging import backup_config

CONFIG_PATH = CONFIG_FILE

# Dynamic thresholds will be set based on balance
TP_MIN_TRADES = 20
FILTER_MIN_TRADES = 10
UPDATE_THRESHOLD = 0.2


def evaluate_best_config(days=7):
    if not os.path.exists(EXPORT_PATH):
        send_telegram_message(
            escape_markdown_v2("❌ No trade history available for optimization."),
            force=True,
        )
        return

    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        df = df[df["Date"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=days)]

        if df.empty:
            send_telegram_message(escape_markdown_v2("ℹ️ No recent trades for TP analysis."), force=True)
            return

        # Get current balance for adaptive thresholds
        balance = get_cached_balance()

        # Adaptive thresholds based on balance
        tp_min_trades = 10 if balance < 300 else 20
        update_threshold = 0.1 if balance < 300 else 0.2

        total = len(df)

        # Skip if not enough trades
        if total < tp_min_trades:
            send_telegram_message(escape_markdown_v2(f"ℹ️ Not enough trades for TP optimization (need {tp_min_trades}, have {total})"), force=True)
            return

        tp1_hits = df[df["TP1 Hit"] == "YES"]
        tp2_hits = df[df["TP2 Hit"] == "YES"]
        sl_hits = df[df["SL Hit"] == "YES"]
        avg_pnl = df["PnL (%)"].mean()

        tp1_winrate = round(len(tp1_hits) / total * 100, 1)
        tp2_winrate = round(len(tp2_hits) / total * 100, 1)
        sl_rate = round(len(sl_hits) / total * 100, 1)

        msg = (
            f"📊 *TP/SL Performance ({days}d)*\n"
            f"Balance: ${balance:.2f}\n"
            f"Total Trades: {total}\n"
            f"• TP1 hit: {len(tp1_hits)} ({tp1_winrate}%)\n"
            f"• TP2 hit: {len(tp2_hits)} ({tp2_winrate}%)\n"
            f"• SL hit: {len(sl_hits)} ({sl_rate}%)\n"
            f"• Avg PnL: {avg_pnl:.2f}%"
        )
        send_telegram_message(escape_markdown_v2(msg), force=True)

        # Calculate new TP values with updated base for TP2
        new_tp1 = 0.007 + (tp1_winrate - 60) * 0.0002
        new_tp2 = 0.014 + (tp2_winrate - 40) * 0.0003  # Updated from 0.013 to 0.014

        # Apply more aggressive bounds for small accounts
        if balance < 300:
            new_tp1 = max(0.005, min(new_tp1, 0.015))
            new_tp2 = max(0.008, min(new_tp2, 0.025))
        else:
            new_tp1 = max(0.004, min(new_tp1, 0.02))
            new_tp2 = max(0.007, min(new_tp2, 0.035))

        # Check if update is needed based on adaptive threshold
        if abs(new_tp1 - TP1_PERCENT) / TP1_PERCENT > update_threshold or abs(new_tp2 - TP2_PERCENT) / TP2_PERCENT > update_threshold:
            backup_config()
            _update_config_tp(new_tp1, new_tp2)
            send_telegram_message(
                escape_markdown_v2(
                    f"✅ TP1/TP2 auto-updated:\n"
                    f"TP1: {round(new_tp1 * 100, 2)}%\n"
                    f"TP2: {round(new_tp2 * 100, 2)}%\n"
                    f"(Threshold: {update_threshold * 100}% for ${balance:.0f} balance)"
                ),
                force=True,
            )

    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"❌ TP Optimizer Error: {e}"), force=True)


def _update_config_tp(tp1, tp2):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            if line.startswith("TP1_PERCENT"):
                f.write(f"TP1_PERCENT = {round(tp1, 4)}\n")
            elif line.startswith("TP2_PERCENT"):
                f.write(f"TP2_PERCENT = {round(tp2, 4)}\n")
            else:
                f.write(line)


def _update_filter_thresholds(new_thresholds: dict):
    try:
        backup_config()

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"FILTER_THRESHOLDS = ({.*?})", content, re.DOTALL)
        old_data = {}
        if match:
            old_data = eval(match.group(1))
            with open(BACKUP_PATH, "w", encoding="utf-8") as bkp:
                json.dump(old_data, bkp, indent=2)

        new_text = "FILTER_THRESHOLDS = " + json.dumps(new_thresholds, indent=4)
        new_content = re.sub(r"FILTER_THRESHOLDS = ({.*?})", new_text, content, flags=re.DOTALL)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        changes = []
        for symbol, new_vals in new_thresholds.items():
            if symbol in old_data:
                old_vals = old_data[symbol]
                delta = []
                for k in ["atr", "adx", "bb"]:
                    old_v = round(old_vals.get(k, 0), 5)
                    new_v = round(new_vals.get(k, 0), 5)
                    if abs(old_v - new_v) >= 0.0001:
                        delta.append(f"{k.upper()}: {old_v} → {new_v}")
                if delta:
                    changes.append(f"{symbol} → " + " | ".join(delta))

        if changes:
            report = "📊 Filter thresholds updated:\n" + "\n".join(changes)
            send_telegram_message(escape_markdown_v2(report), force=True)
        else:
            send_telegram_message(escape_markdown_v2("ℹ️ No significant filter changes."), force=True)

    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"⚠️ Failed to update config.py: {e}"), force=True)


def _analyze_filter_thresholds():
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]

        # Get balance for adaptive thresholds
        balance = get_cached_balance()
        filter_min_trades = 5 if balance < 300 else 10

        if len(df) < filter_min_trades:
            return

        new_thresholds = {}
        for symbol in df["Symbol"].unique():
            sub = df[df["Symbol"] == symbol]
            if len(sub) < filter_min_trades:
                continue

            winners = sub[sub["Result"].isin(["TP1", "TP2"])]
            avg_atr = round(winners["atr"].mean() / winners["price"].mean(), 5)
            avg_adx = round(winners["adx"].mean(), 1)
            avg_bb = round((winners["bb_width"] / winners["price"]).mean(), 5)

            new_thresholds[symbol] = {"atr": avg_atr, "adx": avg_adx, "bb": avg_bb}

        if new_thresholds:
            _update_filter_thresholds(new_thresholds)

    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"❌ Filter optimizer error: {e}"))


def _analyze_symbol_stats():
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]

        # Get balance for adaptive thresholds
        balance = get_cached_balance()
        min_trades_required = 10 if balance < 300 else 20

        if len(df) < min_trades_required:
            return

        status = {}
        messages = []

        for symbol in df["Symbol"].unique():
            sub = df[df["Symbol"] == symbol]
            if len(sub) < min_trades_required:
                continue

            wins = len(sub[sub["Result"].isin(["TP1", "TP2"])])
            total = len(sub)
            winrate = wins / total * 100
            avg_pnl = sub["PnL (%)"].mean()

            # More lenient thresholds for small accounts
            disable_threshold = 25 if balance < 300 else 30
            priority_threshold = 65 if balance < 300 else 70

            if winrate < disable_threshold and total >= min_trades_required:
                status[symbol] = "disabled"
                messages.append(f"⏸ {symbol} disabled – poor stats (winrate {round(winrate, 1)}%)")
            elif winrate > priority_threshold and avg_pnl > 0.8:
                status[symbol] = "priority"
                messages.append(f"⭐️ {symbol} boosted – winrate {round(winrate, 1)}%, avg PnL {round(avg_pnl, 2)}%")

        if status:
            os.makedirs("data", exist_ok=True)
            with open(STATUS_PATH, "w") as f:
                json.dump(status, f, indent=2)

        if messages:
            send_telegram_message(
                escape_markdown_v2("📌 Symbol Stats:\n" + "\n".join(messages)),
                force=True,
            )

    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"⚠️ Symbol status analysis failed: {e}"), force=True)


def run_tp_optimizer():
    evaluate_best_config()
    _analyze_filter_thresholds()
    _analyze_symbol_stats()
