# tp_optimizer_ml.py — безопасная версия с JSON-конфигом

import datetime
import json
import os
import shutil

import pandas as pd

from common.config_loader import (
    # Если вы хотите хранить ML-пороги в config_loader:
    # TP_ML_THRESHOLD,
    CONFIG_FILE,  # только если надо делать backup
    TP_ML_MIN_TRADES_FULL,
    TP_ML_MIN_TRADES_INITIAL,
    TP_ML_SWITCH_THRESHOLD,
)
from constants import TP_CSV
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
from utils_logging import log

# Файл, где храним обновлённые TP-настройки по символам:
SETTINGS_JSON = "data/tp_settings.json"

# Опциональный backup config_loader.py (если нужно):
BACKUP_FILE = "config_backup.py"


def _load_json_settings():
    """Загрузить tp_settings.json с диска. Если нет — вернуть пустой dict."""
    if not os.path.exists(SETTINGS_JSON):
        return {}
    try:
        with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[TP-ML] Error loading {SETTINGS_JSON}: {e}", level="WARNING")
        return {}


def _save_json_settings(data):
    """Сохранить tp_settings.json (безопасно)."""
    try:
        os.makedirs("data", exist_ok=True)
        with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log(f"[TP-ML] Settings saved to {SETTINGS_JSON}", level="INFO")
    except Exception as e:
        log(f"[TP-ML] Error saving {SETTINGS_JSON}: {e}", level="ERROR")


def _backup_config():
    """При желании создаём backup вашего config_loader.py (или другого файла)."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        backup_name = f"{BACKUP_FILE}.{timestamp}"
        shutil.copy(CONFIG_FILE, backup_name)
        log(f"Config_loader.py backed up: {backup_name}", level="INFO")
    except Exception as e:
        log(f"Error backing up config_loader.py: {e}", level="ERROR")


def _get_min_trades_required(balance, total_trades):
    """Определить минимум сделок, зависящий от баланса и TP_ML_SWITCH_THRESHOLD."""
    if balance < 300:
        initial = 6
        full = 12
    else:
        initial = TP_ML_MIN_TRADES_INITIAL
        full = TP_ML_MIN_TRADES_FULL

    # Если total_trades < TP_ML_SWITCH_THRESHOLD, используем initial, иначе full
    # (Если нужно, поправьте логику сами)
    if total_trades < (TP_ML_SWITCH_THRESHOLD * 100):  # Условно, scale factor
        return initial
    else:
        return full


def analyze_and_optimize_tp():
    """
    Основная функция ML-оптимизации, НЕ меняет config_loader.py:
    - считывает tp_performance.csv
    - оценивает TP1/TP2
    - cохраняет результат в data/tp_settings.json
    """
    try:
        if not os.path.exists(TP_CSV):
            log(f"[TP-ML] {TP_CSV} not found", level="WARNING")
            return

        df = pd.read_csv(TP_CSV, parse_dates=["Date"])
        total_trades = len(df)
        if df.empty or total_trades < 5:
            log("[TP-ML] Not enough trade data for ML optimization", level="WARNING")
            return

        # Текущий баланс
        balance = get_cached_balance()

        # Загрузим текущие локальные настройки (tp_settings.json)
        local_settings = _load_json_settings()

        # При желании: backup вашего config_loader.py
        # _backup_config()

        # Рассчитываем min trades
        min_trades_required = _get_min_trades_required(balance, total_trades)
        report_lines = [
            "🤖 *TP Optimizer ML Report*",
            f"💰 Account Balance: ${balance:.2f}",
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

            # Для маленького баланса — более агрессивные границы
            if balance < 300:
                best_tp1 = round(min(max(avg_tp1 / 100, 0.005), 0.012), 4)
                best_tp2 = round(min(max(avg_tp2 / 100, 0.008), 0.025), 4)
            else:
                best_tp1 = round(min(max(avg_tp1 / 100, 0.004), 0.01), 4)
                best_tp2 = round(min(max(avg_tp2 / 100, 0.01), 0.03), 4)

            report_lines.append(
                f"🔹 *{symbol}*\n"
                f"- TP1 wr: {tp1_wr:.0%}, avg PnL: {avg_tp1:.2f}% → Suggest: {best_tp1:.4f}\n"
                f"- TP2 wr: {tp2_wr:.0%}, avg PnL: {avg_tp2:.2f}% → Suggest: {best_tp2:.4f}\n"
                f"- SL rate: {sl_wr:.0%}, avg SL: {avg_sl:.2f}%"
            )

            # Сохраняем в local_settings.
            local_settings.setdefault(symbol, {})
            local_settings[symbol]["tp1"] = best_tp1
            local_settings[symbol]["tp2"] = best_tp2

            updated = True

        if skipped_symbols:
            report_lines.append("\n⏭️ Skipped (not enough data): " + ", ".join(skipped_symbols))

        # Если что-то обновилось — сохраним и отправим отчёт
        if updated:
            _save_json_settings(local_settings)
            send_telegram_message(escape_markdown_v2("\n\n".join(report_lines)), force=True)
        else:
            msg = f"No symbols met the criteria for TP ML optimization\n" f"(min {min_trades_required} trades, total={total_trades})."
            send_telegram_message(escape_markdown_v2(msg), force=True)

    except Exception as e:
        log(f"[TP-ML] Optimization failed: {str(e)}", level="ERROR")
        send_telegram_message(escape_markdown_v2(f"❌ TP ML optimization failed:\n{e}"), force=True)
