import csv
import os

import pandas as pd

from config import DRY_RUN, EXPORT_PATH, TP_LOG_FILE
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
    direction,
    entry_price,
    exit_price,
    qty,
    tp1_hit,
    tp2_hit,
    sl_hit,
    pnl_percent,
    duration_minutes,
    htf_confirmed,
    atr,
    adx,
    bb_width,
):
    if DRY_RUN:
        log(f"[DRY_RUN] Skipping TP log for {symbol}, PnL: {round(pnl_percent, 2)}%", level="INFO")
        return

    date_str = now_with_timezone().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        date_str,
        symbol,
        direction,
        round(entry_price, 6),
        round(exit_price, 6),
        round(qty, 2),
        tp1_hit,
        tp2_hit,
        sl_hit,
        round(pnl_percent, 2),
        duration_minutes,
        htf_confirmed,
        round(atr, 6),
        round(adx, 6),
        round(bb_width, 6),
    ]

    try:
        # Save main TP log
        file_exists = os.path.isfile(TP_LOG_FILE)
        with open(TP_LOG_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(
                    [
                        "Date",
                        "Symbol",
                        "Direction",
                        "Entry Price",
                        "Exit Price",
                        "Qty",
                        "TP1 Hit",
                        "TP2 Hit",
                        "SL Hit",
                        "PnL (%)",
                        "Duration (min)",
                        "HTF Confirmed",
                        "ATR",
                        "ADX",
                        "BB Width",
                    ]
                )
            writer.writerow(row)

        # Save summary/export log
        file_exists = os.path.isfile(EXPORT_PATH)
        with open(EXPORT_PATH, mode="a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(
                    [
                        "Date",
                        "Symbol",
                        "Direction",
                        "Entry Price",
                        "Exit Price",
                        "Qty",
                        "TP1 Hit",
                        "TP2 Hit",
                        "SL Hit",
                        "PnL (%)",
                        "Duration (min)",
                        "HTF Confirmed",
                        "ATR",
                        "ADX",
                        "BB Width",
                    ]
                )
            writer.writerow(row)

        log(
            f"[REAL_RUN] Logged TP result for {symbol}, PnL: {round(pnl_percent, 2)}%", level="INFO"
        )

    except Exception as e:
        log(f"[TP Logger] Failed to log trade for {symbol}: {e}", level="ERROR")


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
        log(f"[ERROR] Failed to load last trade: {e}")
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


def get_trade_stats():
    if not os.path.exists(EXPORT_PATH):
        return 0, 0.0
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        total = len(df)
        win = len(df[df["Result"].isin(["TP1", "TP2"])])
        return total, (win / total) if total else 0.0
    except Exception as e:
        log(f"[ERROR] Failed to read trade stats: {e}")
        return 0, 0.0
