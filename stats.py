# stats.py
import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd

from config import TIMEZONE, is_aggressive, trade_stats, trade_stats_lock  # Added trade_stats_lock
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from tp_optimizer import run_tp_optimizer

EXPORT_PATH = "data/tp_performance.csv"


def now_with_timezone():
    return datetime.now(TIMEZONE)


def format_report_header(title: str) -> str:
    return f"\n{title}\n" + ("-" * 30)


def get_mode_label() -> str:
    return "AGGRESSIVE" if is_aggressive else "SAFE"


# Added: Helper function to get stats safely and reduce duplication
# Reason: Ensures thread safety and simplifies report generation
def get_safe_stats():
    with trade_stats_lock:
        return {
            "total": trade_stats["total"],
            "wins": trade_stats["wins"],
            "losses": trade_stats["losses"],
            "pnl": round(trade_stats["pnl"], 2),
            "withdrawals": round(trade_stats.get("withdrawals", 0), 2),
            "deposits_today": trade_stats.get("deposits_today", 0),
            "streak_loss": trade_stats["streak_loss"],
            "last_trade_summary": trade_stats.get("last_trade_summary", "No trade data."),
        }


def build_performance_report(title: str, period: str):
    stats = get_safe_stats()
    winrate = round((stats["wins"] / stats["total"]) * 100, 1) if stats["total"] else 0
    streak_str = (
        f"{abs(stats['streak_loss'])} wins"
        if stats["streak_loss"] < 0
        else (f"{stats['streak_loss']} losses" if stats["streak_loss"] > 0 else "-")
    )
    mode = get_mode_label()

    if stats["total"] == 0:
        comment = "Not much action yet - waiting for signals."
    elif winrate >= 65 and stats["pnl"] > 2:
        comment = "Great day! Strategy working well."
    elif winrate < 40 and stats["pnl"] < 0:
        comment = "High loss rate - consider reviewing risk."
    else:
        comment = "Trading steady. Monitor performance."

    report = (
        f"📊 *{title}*\n"
        f"Trades: {stats['total']} (W: {stats['wins']} / L: {stats['losses']})\n"
        f"PnL: {'+' if stats['pnl'] >= 0 else ''}{stats['pnl']} USDC\n"
        f"Withdrawals: {stats['withdrawals']} USDC\n"
        f"Winrate: {winrate}%\n"
        f"Streak: {streak_str}\n"
        f"Mode: {mode}\n"
        f"{comment}\n"
        f"Period: {period}"
    )
    return report.encode("utf-8", errors="ignore").decode("utf-8")


def generate_summary():
    stats = get_safe_stats()
    winrate = f"{(stats['wins'] / stats['total'] * 100):.0f}%" if stats["total"] > 0 else "0%"
    date = datetime.now().strftime("%d.%m.%Y")

    summary = f"""
📊 *Current Bot Summary*

📈 *Trades:* {stats['total']} (✅ Wins: {stats['wins']} / ❌ Losses: {stats['losses']})
💰 *PnL:* {stats['pnl']:.2f} USDC
📥 *Deposits:* {stats['deposits_today']} USDC
📤 *Withdrawals:* {stats['withdrawals']} USDC
🎯 *Winrate:* {winrate}
🔥 *Streak:* {stats['streak_loss']}

⚙️ *Mode:* {get_mode_label()}
🕒 *Period:* {date}

🧾 *Last trade summary:*
{stats['last_trade_summary']}
"""
    return summary.strip()


def export_trade_log():
    stats = get_safe_stats()
    try:
        with open("data/trade_log.txt", "a") as f:
            timestamp = now_with_timezone().strftime("%Y-%m-%d %H:%M")
            f.write(
                f"[{timestamp}] Total: {stats['total']}, Wins: {stats['wins']}, "
                f"Losses: {stats['losses']}, PnL: {stats['pnl']}, Withdrawals: {stats['withdrawals']}\n"
            )
        send_telegram_message(escape_markdown_v2("Trade log exported."), force=True)
    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"Failed to export trade log: {e}"), force=True)


def send_daily_report():
    today = now_with_timezone().strftime("%d.%m.%Y")
    msg = build_performance_report("Daily Performance Summary", today)

    if os.path.exists(EXPORT_PATH):
        try:
            # Updated: Added fallback for CSV errors
            # Reason: Prevents crashes if tp_performance.csv is corrupted
            df = (
                pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
                if os.path.exists(EXPORT_PATH)
                else pd.DataFrame()
            )
            df_today = df[df["Date"].dt.date == now_with_timezone().date()]
            if not df_today.empty:
                df_today["PnL (%)"] = pd.to_numeric(df_today["PnL (%)"], errors="coerce")
                avg_by_symbol = (
                    df_today.groupby("Symbol")["PnL (%)"].mean().sort_values(ascending=False)
                )
                best = avg_by_symbol.head(2)
                worst = avg_by_symbol.tail(2)

                def format_line(items):
                    return ", ".join(
                        [
                            f"{sym} ({'+' if v >= 0 else ''}{round(v, 1)}%)"
                            for sym, v in items.items()
                        ]
                    )

                msg += f"\n\nBest: {format_line(best)}"
                msg += f"\nWorst: {format_line(worst)}"
        except Exception as e:
            msg += f"\nError parsing stats: {str(e)}"

    send_telegram_message(escape_markdown_v2(msg), force=True)


def send_weekly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=7)).strftime("%d.%m")
    msg = build_performance_report("Weekly Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)


def should_run_optimizer():
    if not os.path.exists(EXPORT_PATH):
        return False
    try:
        # Updated: Added fallback for CSV errors
        # Reason: Ensures function doesn’t fail on corrupted data
        df = (
            pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
            if os.path.exists(EXPORT_PATH)
            else pd.DataFrame()
        )
        df = df[df["Date"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=2)]
        recent_trades = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        return len(recent_trades) >= 20
    except Exception:
        return False


def start_report_loops():
    def daily_loop():
        while True:
            t = now_with_timezone()
            if t.hour == 21 and t.minute == 0:
                send_daily_report()
                time.sleep(60)
            time.sleep(10)

    def weekly_loop():
        while True:
            t = now_with_timezone()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                send_weekly_report()
                time.sleep(60)
            time.sleep(10)

    def optimizer_loop():
        while True:
            t = now_with_timezone()
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                else:
                    send_telegram_message(
                        escape_markdown_v2("Not enough recent trades to optimize (min: 20)"),
                        force=True,
                    )
                time.sleep(60)
            time.sleep(10)

    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()
