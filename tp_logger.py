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
                    "Qty",
                    "TP1 Hit",
                    "TP2 Hit",
                    "SL Hit",
                    "PnL (%)",
                    "Result",
                    "Held (min)",
                    "HTF Confirmed",
                    "ATR",
                    "ADX",
                    "BB Width",
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
    # Log to console even in DRY_RUN for debugging
    log(
        f"[{'DRY_RUN' if DRY_RUN else 'REAL_RUN'}] Logging trade for {symbol}, PnL: {round(pnl_percent, 2)}%",
        level="INFO",
    )

    if DRY_RUN:
        return  # Skip file write in DRY_RUN, but log to console

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
        "TP1" if tp1_hit else "TP2" if tp2_hit else "SL" if sl_hit else "MANUAL",
        duration_minutes,
        htf_confirmed,
        round(atr, 6),
        round(adx, 6),
        round(bb_width, 6),
    ]

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(TP_LOG_FILE), exist_ok=True)

        # Write to TP_LOG_FILE and EXPORT_PATH
        for path in [TP_LOG_FILE, EXPORT_PATH]:
            file_exists = os.path.isfile(path)
            with open(path, mode="a", newline="") as file:
                writer = csv.writer(file)
                if not file_exists:
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
                            "PnL (%)",
                            "Result",
                            "Held (min)",
                            "HTF Confirmed",
                            "ATR",
                            "ADX",
                            "BB Width",
                        ]
                    )
                writer.writerow(row)

        log(
            f"[REAL_RUN] Logged TP result for {symbol}, PnL: {round(pnl_percent, 2)}% to {TP_LOG_FILE}",
            level="INFO",
        )

    except Exception as e:
        log(f"[TP Logger] Failed to log trade for {symbol}: {e}", level="ERROR")
        from telegram.telegram_utils import send_telegram_message

        send_telegram_message(f"❌ Failed to log trade for {symbol}: {str(e)}", force=True)


def get_last_trade():
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
        # Read CSV, skip rows with invalid date formats
        df = pd.read_csv(EXPORT_PATH)
        # Filter rows where 'Date' matches the expected format
        df = df[df["Date"].str.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", na=False)]
        if df.empty:
            log("[INFO] No valid trade records found in tp_performance.csv", level="INFO")
            return 0, 0.0
        # Parse dates, coercing errors to NaT and dropping invalid rows
        df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df = df.dropna(subset=["Date"])
        # Filter valid trade results
        df = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        total = len(df)
        win = len(df[df["Result"].isin(["TP1", "TP2"])])
        return total, (win / total) if total else 0.0
    except Exception as e:
        log(f"[ERROR] Failed to read trade stats: {e}", level="INFO")
        return 0, 0.0
