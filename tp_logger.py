import csv
import os

from config import EXPORT_PATH, TP_LOG_FILE
from stats import now_with_timezone
from utils_logging import log


def ensure_log_exists():
    if not os.path.exists(EXPORT_PATH):
        with open(EXPORT_PATH, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Date",
                    "Symbol",
                    "Side",
                    "Entry Price",
                    "Exit Price",
                    "TP1 Hit",
                    "TP2 Hit",
                    "SL Hit",
                    "PnL (%)",
                    "Result",
                    "Held (min)",
                    "atr",
                    "adx",
                    "bb_width",
                    "price",
                ]
            )


def log_trade_result(
    symbol,
    side,
    entry_price,
    exit_price,
    result,
    pnl_percent,
    duration_minutes,
    atr,
    adx,
    bb_width,
    price,
    hit_tp1,
    hit_tp2,
    hit_sl,
    htf_trend,  # добавлено
):
    timestamp = now_with_timezone().strftime("%Y-%m-%d %H:%M")

    row = [
        timestamp,
        symbol,
        side,
        entry_price,
        exit_price,
        result,
        round(pnl_percent, 2),
        duration_minutes,
        round(atr, 6),
        round(adx, 6),
        round(bb_width, 6),
        round(price, 6),
        "YES" if hit_tp1 else "NO",
        "YES" if hit_tp2 else "NO",
        "YES" if hit_sl else "NO",
        "YES" if htf_trend else "NO",  # добавлено
    ]

    header = [
        "Date",
        "Symbol",
        "Side",
        "Entry Price",
        "Exit Price",
        "Result",
        "PnL (%)",
        "Duration (min)",
        "ATR",
        "ADX",
        "BB Width",
        "Price",
        "Hit TP1",
        "Hit TP2",
        "Hit SL",
        "HTF Confirmed",  # добавлено
    ]

    file_exists = os.path.isfile(TP_LOG_FILE)

    try:
        with open(TP_LOG_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)
        log(f"TP result logged: {row}", level="INFO")
    except Exception as e:
        log(f"Failed to write TP log: {e}", level="ERROR")


def get_last_trade():
    import pandas as pd

    if not os.path.exists(EXPORT_PATH):
        return None
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return None
        return df.iloc[-1]
    except (pd.errors.EmptyDataError, ValueError) as e:
        log(f"[ERROR] Failed to load last trade: {e}")  # Добавляем логирование
        return None


def get_human_summary_line():
    import pandas as pd

    if not os.path.exists(EXPORT_PATH):
        return "No trade data."
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return "No trades yet."
        last = df.iloc[-1]
        result = last["Result"]
        symbol = last["Symbol"]
        pnl = last["PnL (%)"]
        held = last.get("Held (min)", "?")
        return f"{symbol} — {result} ({pnl:.2f}%), held {held} min"
    except Exception as e:
        return f"Summary error: {e}"
