import csv
import os
from threading import Lock

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH, TP_LOG_FILE
from utils_core import extract_symbol
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
    atr: float = 0.0,
    pair_type: str = "unknown",
    commission: float = 0.0,
    net_pnl: float = 0.0,
    absolute_profit: float = 0.0,
):
    """
    Низкоуровневая запись сделки в tp_performance.csv.
    Пишет расширенные поля и обновляет статистику дня.
    """
    symbol = extract_symbol(symbol)

    if DRY_RUN:
        return

    try:
        import math

        from stats import now_with_timezone

        timestamp = now_with_timezone()
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        final_result = result_type.upper() if result_type else "MANUAL"

        # Уникальный ключ для исключения дубликатов
        trade_key = f"{symbol}_{entry_price}_{exit_price}_{qty}"
        with logged_trades_lock:
            if trade_key in logged_trades:
                log(f"[TP Logger] Duplicate trade, skipping: {trade_key}", level="DEBUG")
                return
            logged_trades.add(trade_key)

        # Чистим NaN (на всякий случай)
        if math.isnan(net_pnl):
            net_pnl = 0.0
        if math.isnan(absolute_profit):
            absolute_profit = 0.0

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
            round(pnl_percent, 2),
            final_result,
            duration_minutes,
            round(commission, 4),
            round(net_pnl, 2),
            round(absolute_profit, 2),
            pair_type,
            round(atr, 5),
            exit_reason or "",
        ]

        header = [
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
            "Type",
            "ATR",
            "Exit Reason",
        ]

        for path in [TP_LOG_FILE, EXPORT_PATH]:
            exists = os.path.isfile(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", newline="") as f:
                writer = csv.writer(f)
                if not exists:
                    writer.writerow(header)
                writer.writerow(row)

        log(
            f"[REAL_RUN] {symbol} {final_result}: PnL={pnl_percent:.2f}%, "
            f"Net={net_pnl:.2f}%, Abs={absolute_profit:.2f}, ATR={atr:.3f}, "
            f"Type={pair_type}, Reason={exit_reason or 'None'}",
            level="INFO",
        )

        # 📊 Обновляем дневную статистику
        with daily_stats_lock:
            daily_trade_stats["count"] += 1
            daily_trade_stats["commission_total"] += commission
            daily_trade_stats["profit_total"] += absolute_profit
            if net_pnl > 0:
                daily_trade_stats["win"] += 1
            else:
                daily_trade_stats["loss"] += 1

    except Exception as e:
        log(f"[TP Logger] Error writing trade for {symbol}: {e}", level="ERROR")


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


def get_today_pnl_from_csv() -> float:
    """
    Считает суммарную прибыль/убыток за сегодня по tp_performance.csv.
    Возвращает сумму в USDC.
    """
    if not os.path.exists(EXPORT_PATH):
        return 0.0
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty or "Date" not in df.columns or "Absolute Profit" not in df.columns:
            return 0.0

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        today = pd.Timestamp.now().normalize()

        df_today = df[df["Date"] >= today]
        total_pnl = df_today["Absolute Profit"].sum()

        return round(total_pnl, 2)
    except Exception as e:
        log(f"[TP Logger] Error reading today PnL: {e}", level="ERROR")
        return 0.0
