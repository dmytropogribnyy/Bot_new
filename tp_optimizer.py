import os

import pandas as pd

from common.config_loader import CONFIG_FILE, EXPORT_PATH, TP1_PERCENT, TP2_PERCENT
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
from utils_logging import backup_config

CONFIG_PATH = CONFIG_FILE


def evaluate_best_config(days=7):
    """
    Анализирует сделки за 'days' дней и при необходимости
    меняет TP1_PERCENT / TP2_PERCENT в config.py.
    """
    if not os.path.exists(EXPORT_PATH):
        send_telegram_message("❌ No trade history found for optimization.", force=True)
        return

    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        # Отбираем сделки за последние days дней
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        df = df[df["Date"] >= cutoff]

        if df.empty:
            send_telegram_message("ℹ️ No recent trades for TP analysis.", force=True)
            return

        # Смотрим баланс — определяем, сколько сделок нужно
        balance = get_cached_balance()
        tp_min_trades = 10 if balance < 300 else 20
        update_threshold = 0.1 if balance < 300 else 0.2

        total = len(df)
        if total < tp_min_trades:
            send_telegram_message(f"ℹ️ Not enough trades for TP optimization (need {tp_min_trades}, have {total})", force=True)
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

        new_tp1 = 0.007 + (tp1_winrate - 60) * 0.0002
        new_tp2 = 0.014 + (tp2_winrate - 40) * 0.0003

        if balance < 300:
            new_tp1 = max(0.005, min(new_tp1, 0.015))
            new_tp2 = max(0.008, min(new_tp2, 0.025))
        else:
            new_tp1 = max(0.004, min(new_tp1, 0.02))
            new_tp2 = max(0.007, min(new_tp2, 0.035))

        diff_tp1 = abs(new_tp1 - TP1_PERCENT) / max(TP1_PERCENT, 0.00001)
        diff_tp2 = abs(new_tp2 - TP2_PERCENT) / max(TP2_PERCENT, 0.00001)

        if diff_tp1 > update_threshold or diff_tp2 > update_threshold:
            backup_config()
            _update_config_tp(new_tp1, new_tp2)

            note = (
                f"✅ TP1/TP2 auto-updated:\n" f"TP1: {round(new_tp1 * 100, 2)}%\n" f"TP2: {round(new_tp2 * 100, 2)}%\n" f"(Threshold: {update_threshold * 100}% for balance ~${int(balance)})"
            )
            send_telegram_message(escape_markdown_v2(note), force=True)

    except Exception as e:
        send_telegram_message(f"❌ TP Optimizer Error: {e}", force=True)


def _update_config_tp(tp1, tp2):
    """
    Заменяет TP1_PERCENT и TP2_PERCENT в config.py на новые значения.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith("TP1_PERCENT"):
                f.write(f"TP1_PERCENT = {round(tp1, 4)}\n")
            elif line.strip().startswith("TP2_PERCENT"):
                f.write(f"TP2_PERCENT = {round(tp2, 4)}\n")
            else:
                f.write(line)


def run_tp_optimizer():
    """
    Главная точка входа: вызывает анализ TP1/TP2.
    """
    evaluate_best_config()
