import csv
import os
from threading import Lock

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH, TAKER_FEE_RATE, TP_LOG_FILE
from stats import now_with_timezone
from utils_core import normalize_symbol
from utils_logging import log

# ===========================
# Globals for duplication & stats
# ===========================
logged_trades = set()
logged_trades_lock = Lock()

daily_trade_stats = {
    "count": 0,
    "win": 0,
    "loss": 0,
    "commission_total": 0.0,
    "profit_total": 0.0,
}
daily_stats_lock = Lock()


def ensure_log_exists():
    """
    Создаёт файлы лога сделок (EXPORT_PATH) при их отсутствии
    (с заголовком CSV).
    """
    if not os.path.exists(EXPORT_PATH):
        os.makedirs(os.path.dirname(EXPORT_PATH), exist_ok=True)
        with open(EXPORT_PATH, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Date",
                    "Symbol",
                    "Side",
                    "Entry Price",
                    "Exit Price",
                    "Qty",
                    "TP1 Hit",
                    "TP2 Hit",
                    "SL Hit",
                    "PnL (%)",  # До комиссий (грубый процент)
                    "Result",
                    "Held (min)",
                    "Commission",
                    "Net PnL (%)",  # После учёта комиссии
                    "Absolute Profit",  # USDC
                ]
            )


def log_trade_result(
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    qty: float,
    tp1_hit: bool,
    tp2_hit: bool,
    sl_hit: bool,
    pnl_percent: float,
    duration_minutes: int,
    result_type: str = "manual",
    exit_reason: str = None,
):
    """
    Запись итогов сделки в журналы TP_LOG_FILE и EXPORT_PATH.

    Параметры:
    -----------
    symbol : str
        Тикер (например, BTC/USDC).
    direction : str
        BUY или SELL.
    entry_price : float
        Цена входа.
    exit_price : float
        Цена выхода.
    qty : float
        Объём сделки (количество).
    tp1_hit, tp2_hit, sl_hit : bool
        Флаги, указывающие, сработали ли TP1, TP2 или SL.
    pnl_percent : float
        Прибыль / убыток в процентах (без учёта комиссии).
    duration_minutes : int
        Время удержания позиции в минутах.
    result_type : str
        Тип результата (tp1, tp2, sl, soft_exit, trailing, manual, auto_profit и т.д.).
    exit_reason : str, optional
        Доп. причина закрытия (для Telegram-сообщения).

    Возвращает:
    -----------
    float : absolute_profit
        Абсолютная прибыль (может быть отрицательной), в USDC.
    """
    symbol = normalize_symbol(symbol)

    try:
        # Логируем в консоль всегда (даже в DRY_RUN)
        log(
            f"[{'DRY_RUN' if DRY_RUN else 'REAL_RUN'}] Logging trade {symbol}, PnL: {round(pnl_percent, 2)}%",
            level="INFO",
        )

        # Если DRY_RUN, не записываем в файл
        if DRY_RUN:
            return 0.0

        # Проверка валидности
        if any(v is None for v in [symbol, direction, entry_price, exit_price, qty]):
            log(
                f"Skipping trade log - invalid data: symbol={symbol}, " f"direction={direction}, entry={entry_price}, exit={exit_price}, qty={qty}",
                level="ERROR",
            )
            return 0.0

        # Считаем комиссию (предполагаем рыночную сделку на вход и выход)
        commission = qty * entry_price * TAKER_FEE_RATE * 2  # "2" → вход+выход

        # Абсолютный профит (до вычитания комиссии)
        price_change = abs(exit_price - entry_price) * qty

        # Если цена ушла против направления, profit будет отрицательным
        if (direction.upper() == "BUY" and exit_price < entry_price) or (direction.upper() == "SELL" and exit_price > entry_price):
            price_change = -price_change

        absolute_profit = price_change - commission

        # Пересчитаем net PnL (%) = pnl_percent (без комиссии) - комиссия в %
        commission_pct = (commission / (qty * entry_price)) * 100
        net_pnl = pnl_percent - commission_pct

        # Если SELL, то можно инвертировать знак (по желанию)
        if direction.upper() == "SELL":
            net_pnl *= -1

        # Определяем, как назвать Result (в CSV)
        final_result = None
        if result_type == "soft_exit":
            final_result = "SOFT_EXIT"
        elif result_type == "trailing":
            final_result = "TRAILING"
        elif result_type == "auto_profit":
            final_result = "AUTO_PROFIT"
        elif tp1_hit:
            final_result = "TP1"
        elif tp2_hit:
            final_result = "TP2"
        elif sl_hit:
            final_result = "SL"
        else:
            final_result = result_type.upper() if result_type else "MANUAL"

        # Создаём уникальный ID для защиты от дублей
        timestamp = now_with_timezone()
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        unique_hash = hash(f"{symbol}_{entry_price}_{exit_price}_{qty}_{final_result}_{timestamp.timestamp()}")
        trade_id = f"{symbol}_{date_str}_{final_result}_{unique_hash}"

        # Проверяем, не логировали ли уже
        with logged_trades_lock:
            if trade_id in logged_trades:
                log(f"Skipping duplicate trade {trade_id}", level="DEBUG")
                return 0.0
            logged_trades.add(trade_id)

        # Обновляем статистику за день
        with daily_stats_lock:
            daily_trade_stats["count"] += 1
            daily_trade_stats["commission_total"] += commission
            if net_pnl > 0:
                daily_trade_stats["win"] += 1
                daily_trade_stats["profit_total"] += absolute_profit
            else:
                daily_trade_stats["loss"] += 1
                daily_trade_stats["profit_total"] += absolute_profit

        # Формируем строку для CSV
        row = [
            date_str,
            symbol,
            direction.upper(),
            round(entry_price, 6),
            round(exit_price, 6),
            round(qty, 6),
            tp1_hit,
            tp2_hit,
            sl_hit,
            round(pnl_percent, 2),  # "грубый" PnL до комиссии
            final_result,
            duration_minutes,
            round(commission, 6),
            round(net_pnl, 2),
            round(absolute_profit, 6),
        ]

        # Заголовок CSV (без account_category)
        base_header = [
            "Date",
            "Symbol",
            "Side",
            "Entry Price",
            "Exit Price",
            "Qty",
            "TP1 Hit",
            "TP2 Hit",
            "SL Hit",
            "PnL (%)",
            "Result",
            "Held (min)",
            "Commission",
            "Net PnL (%)",
            "Absolute Profit",
        ]

        # Запишем в оба файла: TP_LOG_FILE и EXPORT_PATH
        for path in [TP_LOG_FILE, EXPORT_PATH]:
            file_exists = os.path.isfile(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, mode="a", newline="") as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(base_header)
                writer.writerow(row)

        # Лог + Telegram
        log(
            f"[REAL_RUN] {symbol} {final_result}. PnL: {pnl_percent:.2f}%, " f"Net PnL: {net_pnl:.2f}%, Commission: {commission:.6f} USDC, " f"Abs Profit: {absolute_profit:.3f} USDC",
            level="INFO",
        )

        from telegram.telegram_utils import send_telegram_message

        emoji = "✅" if net_pnl > 0 else "❌"
        exit_tag = f"[{exit_reason.upper()}]" if exit_reason else ""
        msg = (
            f"{emoji} Trade {final_result}: {symbol} {direction.upper()} {exit_tag}\n"
            f"Entry: {entry_price:.4f} → Exit: {exit_price:.4f}\n"
            f"Net Profit: {net_pnl:.2f}% (${absolute_profit:.3f})\n"
            f"Commission: ${commission:.4f} | Held: {duration_minutes} min"
        )
        send_telegram_message(msg, force=True)

        return absolute_profit

    except Exception as e:
        log(f"[TP Logger] Error logging trade for {symbol}: {e}", level="ERROR")
        from telegram.telegram_utils import send_telegram_message

        send_telegram_message(f"❌ Error logging trade for {symbol}: {str(e)}", force=True)
        return 0.0


def get_last_trade():
    """Возвращает последнюю запись из EXPORT_PATH (или None, если пусто)."""
    if not os.path.exists(EXPORT_PATH):
        return None
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return None
        return df.iloc[-1]
    except (pd.errors.EmptyDataError, ValueError) as e:
        log(f"[ERROR] Failed to load last trade: {e}")
        return None


def get_human_summary_line():
    """
    Возвращает последний трейд в человекочитаемом виде (примерно).
    """
    if not os.path.exists(EXPORT_PATH):
        return "No trade data available."
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return "No trades recorded."
        last = df.iloc[-1]
        result = last["Result"]
        symbol = last["Symbol"]
        pnl = last.get("Net PnL (%)", last.get("PnL (%)", 0.0))
        abs_profit = last.get("Absolute Profit", 0.0)
        held = last.get("Held (min)", "?")

        return f"{symbol} — {result} ({pnl:.2f}%, ${abs_profit:.2f}), held for {held} min"
    except Exception as e:
        return f"Summary error: {e}"


def get_trade_stats():
    """
    Простейшая статистика по логам (кол-во сделок и винрейт).
    """
    if not os.path.exists(EXPORT_PATH):
        return 0, 0.0
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            log("[INFO] No trade records in the CSV", level="INFO")
            return 0, 0.0

        total = len(df)
        if "Net PnL (%)" in df.columns:
            wins = len(df[df["Net PnL (%)"] > 0])
            return total, (wins / total if total else 0.0)
        else:
            # Или используем столбец "PnL (%)" (грубая оценка)
            wins = len(df[df["PnL (%)"] > 0])
            return total, (wins / total if total else 0.0)
    except Exception as e:
        log(f"[ERROR] Failed to read trade statistics: {e}", level="INFO")
        return 0, 0.0


def get_daily_stats():
    """
    Возвращает ежедневную сводку:
    - кол-во сделок, побед, поражений
    - комиссии, профит, чистый профит
    """
    with daily_stats_lock:
        stats = daily_trade_stats.copy()

    if stats["count"] == 0:
        return {
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "win_rate_today": 0.0,
            "profit_today": 0.0,
            "commission_today": 0.0,
            "net_today": 0.0,
        }

    win_rate = stats["win"] / stats["count"]
    return {
        "trades_today": stats["count"],
        "wins_today": stats["win"],
        "losses_today": stats["loss"],
        "win_rate_today": round(win_rate * 100, 2),
        "profit_today": stats["profit_total"],
        "commission_today": stats["commission_total"],
        "net_today": stats["profit_total"] - stats["commission_total"],
    }


def reset_daily_stats():
    """
    Сброс ежедневной статистики (вызов перед новым сутками).
    """
    with daily_stats_lock:
        daily_trade_stats["count"] = 0
        daily_trade_stats["win"] = 0
        daily_trade_stats["loss"] = 0
        daily_trade_stats["commission_total"] = 0.0
        daily_trade_stats["profit_total"] = 0.0


def get_total_trade_count():
    """
    Возвращает общее количество сделок, записанных в EXPORT_PATH.
    """
    if not os.path.exists(EXPORT_PATH):
        return 0
    try:
        df = pd.read_csv(EXPORT_PATH)
        return len(df)
    except Exception as e:
        log(f"[ERROR] Failed to count trades: {e}", level="WARNING")
        return 0
