import csv
import os
from datetime import datetime

from config import EXPORT_PATH, TIMEZONE
from utils import log  #


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
    tp1_hit,
    tp2_hit,
    sl_hit,
    pnl_percent,
    result,
    duration_minutes,
    atr=None,
    adx=None,
    bb_width=None,
    price=None,
):
    ensure_log_exists()
    with open(EXPORT_PATH, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M"),
                symbol,
                side,
                round(entry_price, 5),
                round(exit_price, 5),
                "YES" if tp1_hit else "NO",
                "YES" if tp2_hit else "NO",
                "YES" if sl_hit else "NO",
                round(pnl_percent, 2),
                result,
                round(duration_minutes, 1),
                atr if atr is not None else "",
                adx if adx is not None else "",
                bb_width if bb_width is not None else "",
                price if price is not None else "",
            ]
        )


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
