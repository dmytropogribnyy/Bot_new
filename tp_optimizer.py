import json
import os
import re

import pandas as pd

from common.config_loader import CONFIG_FILE, EXPORT_PATH, TP1_PERCENT, TP2_PERCENT
from constants import BACKUP_PATH, STATUS_PATH
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
from utils_logging import backup_config

###############################################################################
# ПРЕДУСЛОВИЕ:
# 1. CSV (EXPORT_PATH) должен содержать колонки:
#   - "Date"       (parse_dates=["Date"])
#   - "TP1 Hit", "TP2 Hit", "SL Hit" (значения "YES" или True)
#   - "PnL (%)"    (процент прибыли/убытка)
#   - (для фильтров) "atr", "price", "adx", "bb_width"
#   - (для статусов) "Symbol", "Result" (TP1 / TP2 / SL), "PnL (%)"
#
# 2. В config.py объявлены строки:
#     TP1_PERCENT = 0.007
#     TP2_PERCENT = 0.014
#   ...и опционально:
#     FILTER_THRESHOLDS = { "BTCUSDC": {...}, ... }
#
# 3. Если не нужны фильтры или статусы, можно удалить соответствующие функции.
###############################################################################

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
        # Порог изменения (насколько должна отличаться новая TP1/TP2 в %)
        update_threshold = 0.1 if balance < 300 else 0.2

        total = len(df)
        if total < tp_min_trades:
            send_telegram_message(f"ℹ️ Not enough trades for TP optimization (need {tp_min_trades}, have {total})", force=True)
            return

        # Предполагаем: "TP1 Hit" / "TP2 Hit" / "SL Hit" имеют значение "YES"
        # Если у вас True/False — замените "YES" на True.
        tp1_hits = df[df["TP1 Hit"] == "YES"]
        tp2_hits = df[df["TP2 Hit"] == "YES"]
        sl_hits = df[df["SL Hit"] == "YES"]

        avg_pnl = df["PnL (%)"].mean()

        tp1_winrate = round(len(tp1_hits) / total * 100, 1)
        tp2_winrate = round(len(tp2_hits) / total * 100, 1)
        sl_rate = round(len(sl_hits) / total * 100, 1)

        # Отчёт в Telegram
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

        # Простейшая формула для новых TP
        new_tp1 = 0.007 + (tp1_winrate - 60) * 0.0002
        new_tp2 = 0.014 + (tp2_winrate - 40) * 0.0003

        # Границы для маленького / большого баланса
        if balance < 300:
            new_tp1 = max(0.005, min(new_tp1, 0.015))
            new_tp2 = max(0.008, min(new_tp2, 0.025))
        else:
            new_tp1 = max(0.004, min(new_tp1, 0.02))
            new_tp2 = max(0.007, min(new_tp2, 0.035))

        # Проверка, насколько сильно новые значения отличаются от старых
        diff_tp1 = abs(new_tp1 - TP1_PERCENT) / max(TP1_PERCENT, 0.00001)
        diff_tp2 = abs(new_tp2 - TP2_PERCENT) / max(TP2_PERCENT, 0.00001)

        if diff_tp1 > update_threshold or diff_tp2 > update_threshold:
            backup_config()  # резервная копия config.py
            _update_config_tp(new_tp1, new_tp2)

            note = f"✅ TP1/TP2 auto-updated:\n" f"TP1: {round(new_tp1*100, 2)}%\n" f"TP2: {round(new_tp2*100, 2)}%\n" f"(Threshold: {update_threshold*100}% for balance ~${int(balance)})"
            send_telegram_message(escape_markdown_v2(note), force=True)

    except Exception as e:
        send_telegram_message(f"❌ TP Optimizer Error: {e}", force=True)


def _update_config_tp(tp1, tp2):
    """
    Ищет строки, начинающиеся с TP1_PERCENT и TP2_PERCENT в config.py,
    заменяет на новые значения.
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


def _update_filter_thresholds(new_thresholds: dict):
    """
    Пробует найти FILTER_THRESHOLDS = { ... } в config.py
    и заменить содержимое словаря.
    Нужно, если вы используете dynamic filters (atr / adx / bb).
    """
    try:
        backup_config()

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"FILTER_THRESHOLDS\s*=\s*({.*?})", content, re.DOTALL)
        old_data = {}
        if match:
            # eval, чтобы распарсить объект
            old_data = eval(match.group(1))

            # Сохраняем старые пороги в BACKUP_PATH (JSON)
            with open(BACKUP_PATH, "w", encoding="utf-8") as bkp:
                json.dump(old_data, bkp, indent=2)

        # Формируем новую строку со словарём
        new_text = "FILTER_THRESHOLDS = " + json.dumps(new_thresholds, indent=4)
        new_content = re.sub(r"FILTER_THRESHOLDS\s*=\s*({.*?})", new_text, content, flags=re.DOTALL)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Формируем отчёт об изменениях
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
            send_telegram_message("ℹ️ No significant filter changes.", force=True)

    except Exception as e:
        send_telegram_message(f"⚠️ Failed to update config.py: {e}", force=True)


def _analyze_filter_thresholds():
    """
    Анализирует сделки (TP1/TP2/SL), извлекает средний ATR/ADX/BB
    для выигрышных сделок. Затем вызывает _update_filter_thresholds
    для автоподстройки FILTER_THRESHOLDS.

    Требует в CSV колонки:
      "atr", "price", "adx", "bb_width"
    Если их нет — удалите эту функцию.
    """
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]

        balance = get_cached_balance()
        filter_min_trades = 5 if balance < 300 else 10

        if len(df) < filter_min_trades:
            return  # Недостаточно сделок

        new_thresholds = {}
        for symbol in df["Symbol"].unique():
            sub = df[df["Symbol"] == symbol]
            if len(sub) < filter_min_trades:
                continue

            # Только выигрышные (TP1/TP2)
            winners = sub[sub["Result"].isin(["TP1", "TP2"])]

            # Предполагаем колонки "atr", "price", "adx", "bb_width"
            avg_atr = round((winners["atr"].mean() / winners["price"].mean()), 5)
            avg_adx = round(winners["adx"].mean(), 1)
            avg_bb = round((winners["bb_width"] / winners["price"]).mean(), 5)

            new_thresholds[symbol] = {"atr": avg_atr, "adx": avg_adx, "bb": avg_bb}

        if new_thresholds:
            _update_filter_thresholds(new_thresholds)

    except Exception as e:
        send_telegram_message(f"❌ Filter optimizer error: {e}", force=True)


def _analyze_symbol_stats():
    """
    Проверяет винрейт символа. Если <30% → disabled, если >70%+avg_pnl>0.8 → priority.
    Результат записывает в STATUS_PATH (JSON), отправляет Telegram-уведомление.
    Если не нужно — удалите всю функцию.
    """
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]

        balance = get_cached_balance()
        min_trades_required = 10 if balance < 300 else 20

        if len(df) < min_trades_required:
            return

        status_map = {}
        messages = []

        for symbol in df["Symbol"].unique():
            sub = df[df["Symbol"] == symbol]
            if len(sub) < min_trades_required:
                continue

            wins = len(sub[sub["Result"].isin(["TP1", "TP2"])])
            total = len(sub)
            winrate = wins / total * 100
            avg_pnl = sub["PnL (%)"].mean()

            # Пороги для маленьких / больших счетов
            disable_threshold = 25 if balance < 300 else 30
            priority_threshold = 65 if balance < 300 else 70

            if winrate < disable_threshold:
                status_map[symbol] = "disabled"
                messages.append(f"⏸ {symbol} disabled – poor stats (winrate {winrate:.1f}%)")
            elif winrate > priority_threshold and avg_pnl > 0.8:
                status_map[symbol] = "priority"
                messages.append(f"⭐️ {symbol} boosted – winrate {winrate:.1f}%, avg PnL {avg_pnl:.2f}%")

        if status_map:
            os.makedirs("data", exist_ok=True)
            with open(STATUS_PATH, "w") as f:
                json.dump(status_map, f, indent=2)

        if messages:
            msg = "📌 Symbol Stats:\n" + "\n".join(messages)
            send_telegram_message(escape_markdown_v2(msg), force=True)

    except Exception as e:
        send_telegram_message(f"⚠️ Symbol status analysis failed: {e}", force=True)


def run_tp_optimizer():
    """
    Главная точка входа: вызывает анализ TP1/TP2,
    опциональную адаптацию фильтров и статусов.
    Если не нужны фильтры или статус — закомментируйте соответствующие вызовы.
    """
    evaluate_best_config()  # Авто-настройка TP1/TP2
    _analyze_filter_thresholds()  # <- Удалите/закомментируйте, если не нужны dynamic filters
    _analyze_symbol_stats()  # <- Удалите/закомментируйте, если не нужен priority/disabled
