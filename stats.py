from datetime import datetime, timedelta
from config import trade_stats, TIMEZONE, is_aggressive
from utils import send_telegram_message, escape_markdown_v2
import threading
import time
import pandas as pd
import os
from tp_optimizer import run_tp_optimizer
from tp_logger import get_human_summary_line

EXPORT_PATH = "data/tp_performance.csv"


def now():
    return datetime.now(TIMEZONE)


def format_report_header(title: str) -> str:
    return f"\n{title}\n" + ("-" * 30)


def get_mode_label() -> str:
    return "AGGRESSIVE" if is_aggressive else "SAFE"


def build_performance_report(title: str, period: str):
    total = trade_stats["total"]
    wins = trade_stats["wins"]
    losses = trade_stats["losses"]
    pnl = round(trade_stats["pnl"], 2)
    withdrawals = round(trade_stats.get("withdrawals", 0), 2)
    winrate = round((wins / total) * 100, 1) if total else 0
    streak = trade_stats["streak_loss"]
    mode = get_mode_label()

    streak_str = (
        f"{abs(streak)} wins"
        if streak < 0
        else (f"{streak} losses" if streak > 0 else "-")
    )

    if total == 0:
        comment = "Not much action yet - waiting for signals."
    elif winrate >= 65 and pnl > 2:
        comment = "Great day! Strategy working well."
    elif winrate < 40 and pnl < 0:
        comment = "High loss rate - consider reviewing risk."
    else:
        comment = "Trading steady. Monitor performance."

    report = (
        f"📊 *{title}*\n"
        f"Trades: {total} (W: {wins} / L: {losses})\n"
        f"PnL: {'+' if pnl >= 0 else ''}{pnl} USDC\n"
        f"Withdrawals: {withdrawals} USDC\n"
        f"Winrate: {winrate}%\n"
        f"Streak: {streak_str}\n"
        f"Mode: {mode}\n"
        f"{comment}\n"
        f"Period: {period}"
    )
    return report.encode("utf-8", errors="ignore").decode("utf-8")


def generate_summary():
    today = now().strftime("%d.%m.%Y")
    summary = build_performance_report("Current Bot Summary", today)
    last_trade = get_human_summary_line()
    last_trade = str(last_trade)
    summary += f"\n\nLast trade summary:\n{last_trade}"
    return escape_markdown_v2(summary)


def export_trade_log():
    try:
        with open("data/trade_log.txt", "a") as f:
            timestamp = now().strftime("%Y-%m-%d %H:%M")
            f.write(
                f"[{timestamp}] Total: {trade_stats['total']}, Wins: {trade_stats['wins']}, "
                f"Losses: {trade_stats['losses']}, PnL: {round(trade_stats['pnl'], 2)}, Withdrawals: {round(trade_stats.get('withdrawals', 0), 2)}\n"
            )
        send_telegram_message("Trade log exported.", force=True)
    except Exception as e:
        send_telegram_message(f"Failed to export trade log: {e}", force=True)


def send_daily_report():
    today = now().strftime("%d.%m.%Y")
    msg = build_performance_report("Daily Performance Summary", today)

    if os.path.exists(EXPORT_PATH):
        try:
            df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
            df_today = df[df["Date"].dt.date == now().date()]
            if not df_today.empty:
                df_today["PnL (%)"] = pd.to_numeric(
                    df_today["PnL (%)"], errors="coerce"
                )
                avg_by_symbol = (
                    df_today.groupby("Symbol")["PnL (%)"]
                    .mean()
                    .sort_values(ascending=False)
                )
                best = avg_by_symbol.head(2)
                worst = avg_by_symbol.tail(2)

                def format_line(items):
                    return ", ".join(
                        [
                            f"{sym} ({'+' if v >= 0 else ''}{round(v,1)}%)"
                            for sym, v in items.items()
                        ]
                    )

                msg += f"\n\nBest: {format_line(best)}"
                msg += f"\nWorst: {format_line(worst)}"
        except Exception as e:
            msg += f"\nError parsing stats: {str(e)}"

    send_telegram_message(escape_markdown_v2(msg), force=True)


def send_weekly_report():
    end = now()
    start = (end - timedelta(days=7)).strftime("%d.%m")
    msg = build_performance_report(
        "Weekly Performance Summary", f"{start}-{end.strftime('%d.%m')}"
    )
    send_telegram_message(escape_markdown_v2(msg), force=True)


def should_run_optimizer():
    if not os.path.exists(EXPORT_PATH):
        return False
    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        df = df[df["Date"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=2)]
        recent_trades = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        return len(recent_trades) >= 20
    except:
        return False


def start_report_loops():
    def daily_loop():
        while True:
            t = now()
            if t.hour == 21 and t.minute == 0:
                send_daily_report()
                time.sleep(60)
            time.sleep(10)

    def weekly_loop():
        while True:
            t = now()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                send_weekly_report()
                time.sleep(60)
            time.sleep(10)

    def optimizer_loop():
        while True:
            t = now()
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                else:
                    send_telegram_message(
                        "Not enough recent trades to optimize (min: 20)", force=True
                    )
                time.sleep(60)
            time.sleep(10)

    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()
