import csv
import os
from threading import Lock

import pandas as pd

from common.config_loader import DRY_RUN, EXPORT_PATH, TAKER_FEE_RATE, TP_LOG_FILE
from stats import now_with_timezone
from utils_logging import log

# Global variables for tracking trades with enhanced duplicate prevention
logged_trades = set()
logged_trades_lock = Lock()
daily_trade_stats = {"count": 0, "win": 0, "loss": 0, "commission_total": 0.0, "profit_total": 0.0}
daily_stats_lock = Lock()


def ensure_log_exists():
    """Create trade log files if they don't exist."""
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
                    "PnL (%)",
                    "Result",
                    "Held (min)",
                    "HTF Confirmed",
                    "ATR",
                    "ADX",
                    "BB Width",
                    "Commission",  # Commission column
                    "Net PnL (%)",  # Net profit column (after commission)
                    "Absolute Profit",  # Absolute profit in USDC (for small account tracking)
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
    result_type="manual",
    account_category=None,  # Added parameter
):
    """Log trade result with enhanced commission calculation and duplicate prevention."""
    try:
        # Log to console even in DRY_RUN for debugging
        log(
            f"[{'DRY_RUN' if DRY_RUN else 'REAL_RUN'}] Logging trade {symbol}, PnL: {round(pnl_percent, 2)}%",
            level="INFO",
        )

        if DRY_RUN:
            return  # Skip file writing in DRY_RUN but still log to console

        # Validate input data
        if any(v is None for v in [symbol, direction, entry_price, exit_price, qty]):
            log(f"Skipping trade log - invalid data: symbol={symbol}, direction={direction}, entry={entry_price}, exit={exit_price}, qty={qty}", level="ERROR")
            return

        # Calculate commission (taker for entry and exit)
        commission = qty * entry_price * TAKER_FEE_RATE * 2  # Entry and exit

        # For small accounts: Calculate absolute profit in USDC (important for small account tracking)
        absolute_price_change = abs(exit_price - entry_price) * qty
        absolute_profit = absolute_price_change - commission

        # If price moved against us, absolute profit is negative
        if (direction == "BUY" and exit_price < entry_price) or (direction == "SELL" and exit_price > entry_price):
            absolute_profit = -absolute_profit

        # Calculate percentage price change and net PnL
        price_change_pct = (exit_price - entry_price) / entry_price * 100
        commission_pct = (commission / (qty * entry_price)) * 100
        net_pnl = price_change_pct - commission_pct

        if direction == "SELL":
            net_pnl *= -1
            price_change_pct *= -1

        # Determine result type
        result = result_type.upper() if result_type else "MANUAL"
        if tp1_hit and result_type not in ["soft_exit", "trailing"]:
            result = "TP1"
        elif tp2_hit and result_type not in ["soft_exit", "trailing"]:
            result = "TP2"
        elif sl_hit and result_type not in ["soft_exit", "trailing"]:
            result = "SL"
        elif result_type == "soft_exit":
            result = "SOFT_EXIT"
        elif result_type == "trailing":
            result = "TRAILING"

        # Create unique trade ID with enhanced uniqueness
        timestamp = now_with_timezone()
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        unique_hash = hash(f"{symbol}_{entry_price}_{exit_price}_{qty}_{result}_{timestamp.timestamp()}")
        trade_id = f"{symbol}_{date_str}_{result}_{unique_hash}"

        # Skip if already logged this trade
        with logged_trades_lock:
            # Additional check for similar trades within last minute
            similar_trades = [
                t
                for t in logged_trades
                if t.startswith(f"{symbol}_") and abs(timestamp.timestamp() - float(t.split("_")[-1] if "_" in t and t.split("_")[-1].replace(".", "", 1).isdigit() else 0)) < 60
            ]

            if trade_id in logged_trades or similar_trades:
                log(f"Skipping duplicate trade {trade_id}", level="DEBUG")
                return

            logged_trades.add(trade_id)

        # Update daily statistics
        with daily_stats_lock:
            daily_trade_stats["count"] += 1
            daily_trade_stats["commission_total"] += commission

            if net_pnl > 0:
                daily_trade_stats["win"] += 1
                daily_trade_stats["profit_total"] += absolute_profit
            else:
                daily_trade_stats["loss"] += 1
                daily_trade_stats["profit_total"] += absolute_profit  # Will be negative for losses

        # Составляем строку лога
        row = [
            date_str,
            symbol,
            direction,
            round(entry_price, 6),
            round(exit_price, 6),
            round(qty, 6),  # Increased precision for small quantities
            tp1_hit,
            tp2_hit,
            sl_hit,
            round(price_change_pct, 2),  # Original PnL without commission
            result,
            duration_minutes,
            htf_confirmed,
            round(atr, 6),
            round(adx, 6),
            round(bb_width, 6),
            round(commission, 6),  # Commission
            round(net_pnl, 2),  # Net profit after commission
            round(absolute_profit, 6),  # Absolute profit in USDC
        ]

        # Добавим в конец row, если account_category передан
        if account_category is not None:
            row.append(account_category)

        # Ensure directory exists
        os.makedirs(os.path.dirname(TP_LOG_FILE), exist_ok=True)

        # Создаем header с учётом поля
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
            "HTF Confirmed",
            "ATR",
            "ADX",
            "BB Width",
            "Commission",
            "Net PnL (%)",
            "Absolute Profit",
        ]

        if account_category is not None:
            base_header.append("Account Category")

        # Write to both TP_LOG_FILE and EXPORT_PATH
        for path in [TP_LOG_FILE, EXPORT_PATH]:
            file_exists = os.path.isfile(path)
            with open(path, mode="a", newline="") as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(base_header)
                writer.writerow(row)

        # Enhanced logging with different messages for different result types
        if result_type == "recovered":
            log(
                f"[Recovered Log] {symbol} closed outside tracked logic. PnL: {round(price_change_pct, 2)}%, " f"Net: {round(net_pnl, 2)}%, Profit: {round(absolute_profit, 6)} USDC",
                level="WARNING",
            )
        elif result_type == "micro_profit":
            log(
                f"[Micro-Profit] {symbol} closed at micro target. PnL: {round(price_change_pct, 2)}%, " f"Net: {round(net_pnl, 2)}%, Profit: {round(absolute_profit, 6)} USDC",
                level="INFO",
            )
        else:
            log(
                f"[REAL_RUN] Recorded result for {symbol}, PnL: {round(price_change_pct, 2)}%, "
                f"Net PnL: {round(net_pnl, 2)}%, Commission: {round(commission, 6)} USDC, "
                f"Absolute Profit: {round(absolute_profit, 6)} USDC",
                level="INFO",
            )

        # Telegram notification with key metrics
        from telegram.telegram_utils import send_telegram_message

        emoji = "✅" if net_pnl > 0 else "❌"
        msg = (
            f"{emoji} Trade {result}: {symbol} {direction}\n"
            f"Entry: {entry_price:.6f} → Exit: {exit_price:.6f}\n"
            f"Net Profit: {net_pnl:.2f}% (${absolute_profit:.3f})\n"
            f"Commission: ${commission:.6f} | Held: {duration_minutes} min"
        )
        send_telegram_message(msg, force=True)

        return absolute_profit  # Return absolute profit for further processing

    except Exception as e:
        log(f"[TP Logger] Error logging trade for {symbol}: {e}", level="ERROR")
        from telegram.telegram_utils import send_telegram_message

        send_telegram_message(f"❌ Error logging trade for {symbol}: {str(e)}", force=True)
        return 0


def get_last_trade():
    """Get the last trade from logs."""
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
    """Get a summary of the last trade in human-readable format."""
    if not os.path.exists(EXPORT_PATH):
        return "No trade data available."
    try:
        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return "No trades recorded."
        last = df.iloc[-1]
        result = last["Result"]
        symbol = last["Symbol"]

        # Use net profit if available
        if "Net PnL (%)" in last:
            pnl = last["Net PnL (%)"]
        else:
            pnl = last["PnL (%)"]

        # Use absolute profit if available (better for small accounts)
        abs_profit_text = ""
        if "Absolute Profit" in last:
            abs_profit = last["Absolute Profit"]
            abs_profit_text = f", ${abs_profit:.3f}"

        held = last.get("Held (min)", "?")
        return f"{symbol} — {result} ({pnl:.2f}%{abs_profit_text}), held for {held} min"
    except Exception as e:
        return f"Summary error: {e}"


def get_trade_stats():
    """Get trade statistics: count and win rate with improved calculations for small accounts."""
    if not os.path.exists(EXPORT_PATH):
        return 0, 0.0
    try:
        df = pd.read_csv(EXPORT_PATH)
        df = df[df["Date"].str.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", na=False) & ~df["Date"].str.startswith("#", na=False)]
        if df.empty:
            log("[INFO] No trade records found in tp_performance.csv", level="INFO")
            return 0, 0.0

        df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df = df.dropna(subset=["Date"])

        # Include SOFT_EXIT and TRAILING as valid results
        df = df[df["Result"].isin(["TP1", "TP2", "SL", "MANUAL", "SOFT_EXIT", "TRAILING"])]
        total = len(df)

        # TP1, TP2 and SOFT_EXIT count as wins
        win = len(df[df["Result"].isin(["TP1", "TP2", "SOFT_EXIT"])])

        # Check by net profit if available (more accurate)
        if "Net PnL (%)" in df.columns:
            profitable_trades = len(df[df["Net PnL (%)"] > 0])
            win_rate_by_pnl = profitable_trades / total if total else 0

            # Enhanced metrics for small accounts analysis
            if "Absolute Profit" in df.columns:
                total_profit = df["Absolute Profit"].sum()
                total_commission = df["Commission"].sum() if "Commission" in df.columns else 0
                avg_profit = df[df["Net PnL (%)"] > 0]["Absolute Profit"].mean() if len(df[df["Net PnL (%)"] > 0]) > 0 else 0
                avg_loss = df[df["Net PnL (%)"] <= 0]["Absolute Profit"].mean() if len(df[df["Net PnL (%)"] <= 0]) > 0 else 0

                log(f"[Stats] Total profit: ${total_profit:.2f}, Commissions: ${total_commission:.2f}, " f"Avg win: ${avg_profit:.2f}, Avg loss: ${avg_loss:.2f}", level="INFO")

            return total, max(win / total if total else 0, win_rate_by_pnl)

        return total, (win / total) if total else 0.0
    except Exception as e:
        log(f"[ERROR] Failed to read trade statistics: {e}", level="INFO")
        return 0, 0.0


def get_daily_stats():
    """Get today's trading statistics (especially useful for small accounts)."""
    with daily_stats_lock:
        stats = daily_trade_stats.copy()

    win_rate = stats["win"] / stats["count"] if stats["count"] > 0 else 0

    return {
        "trades_today": stats["count"],
        "wins_today": stats["win"],
        "losses_today": stats["loss"],
        "win_rate_today": win_rate * 100,
        "profit_today": stats["profit_total"],
        "commission_today": stats["commission_total"],
        "net_today": stats["profit_total"] - stats["commission_total"],
    }


def reset_daily_stats():
    """Reset daily statistics (call at midnight)."""
    with daily_stats_lock:
        daily_trade_stats["count"] = 0
        daily_trade_stats["win"] = 0
        daily_trade_stats["loss"] = 0
        daily_trade_stats["commission_total"] = 0.0
        daily_trade_stats["profit_total"] = 0.0
