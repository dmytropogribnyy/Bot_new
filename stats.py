# stats.py (обновлённый с расширенными отчётами)

import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd

from config import (
    AGGRESSIVENESS_THRESHOLD,
    LOG_LEVEL,
    TIMEZONE,
    trade_stats,
    trade_stats_lock,
)

# Добавляем AGGRESSIVENESS_THRESHOLD
from core.aggressiveness_controller import get_aggressiveness_score  # Добавляем импорт
from htf_optimizer import analyze_htf_winrate
from score_heatmap import generate_score_heatmap
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from tp_optimizer import run_tp_optimizer
from tp_optimizer_ml import analyze_and_optimize_tp
from utils_logging import log  # Добавляем импорт для логирования

EXPORT_PATH = "data/tp_performance.csv"


def now_with_timezone():
    return datetime.now(TIMEZONE)


def format_report_header(title: str) -> str:
    return f"\n{title}\n" + ("-" * 30)


def get_mode_label():
    return "AGGRESSIVE" if get_aggressiveness_score() > AGGRESSIVENESS_THRESHOLD else "SAFE"


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
        comment = "Great period! Strategy working well."
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
        if LOG_LEVEL == "DEBUG":
            log("Trade log exported successfully.", level="DEBUG")
    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"Failed to export trade log: {e}"), force=True)
        log(f"Failed to export trade log: {e}", level="ERROR")


def send_daily_report():
    today = now_with_timezone().strftime("%d.%m.%Y")
    msg = build_performance_report("Daily Performance Summary", today)
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent daily report for {today}.", level="DEBUG")


def send_weekly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=7)).strftime("%d.%m")
    msg = build_performance_report("Weekly Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent weekly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_monthly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=30)).strftime("%d.%m")
    msg = build_performance_report(
        "Monthly Performance Summary", f"{start}-{end.strftime('%d.%m')}"
    )
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent monthly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_quarterly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=90)).strftime("%d.%m")
    msg = build_performance_report(
        "3-Month Performance Summary", f"{start}-{end.strftime('%d.%m')}"
    )
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent quarterly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_halfyear_report():
    end = now_with_timezone()
    start = (end - timedelta(days=180)).strftime("%d.%m")
    msg = build_performance_report(
        "6-Month Performance Summary", f"{start}-{end.strftime('%d.%m')}"
    )
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent half-year report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_yearly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=365)).strftime("%d.%m")
    msg = build_performance_report("Yearly Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent yearly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def should_run_optimizer():
    if not os.path.exists(EXPORT_PATH):
        return False
    try:
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        df = df[df["Date"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=2)]
        recent_trades = df[df["Result"].isin(["TP1", "TP2", "SL"])]
        return len(recent_trades) >= 20
    except Exception as e:
        log(f"Error checking optimizer condition: {e}", level="ERROR")
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

    def extended_reports_loop():
        while True:
            t = now_with_timezone()
            if t.day == 1 and t.hour == 21 and t.minute == 0:
                send_monthly_report()
            if (
                t.day == 1 and t.month in [1, 4, 7, 10] and t.hour == 21 and t.minute == 5
            ):  # Исправляем of на in
                send_quarterly_report()
            if (
                t.day == 1 and t.month in [1, 7] and t.hour == 21 and t.minute == 10
            ):  # Исправляем of на in
                send_halfyear_report()
            if t.day == 1 and t.month == 1 and t.hour == 21 and t.minute == 15:
                send_yearly_report()
            time.sleep(10)

    def optimizer_loop():
        while True:
            t = now_with_timezone()
            if t.day % 2 == 0 and t.hour == 21 and t.minute == 30:
                if should_run_optimizer():
                    run_tp_optimizer()
                    analyze_and_optimize_tp()
                else:
                    send_telegram_message(
                        escape_markdown_v2("Not enough recent trades to optimize (min: 20)"),
                        force=True,
                    )
                time.sleep(60)
            time.sleep(10)

    def heatmap_loop():
        while True:
            t = now_with_timezone()
            if t.weekday() == 4 and t.hour == 20 and t.minute == 0:
                generate_score_heatmap(days=7)
                time.sleep(60)
            time.sleep(10)

    def htf_optimizer_loop():
        while True:
            t = now_with_timezone()
            if t.weekday() == 6 and t.hour == 21 and t.minute == 0:
                analyze_htf_winrate()
                time.sleep(60)
            time.sleep(10)

    threading.Thread(target=daily_loop, daemon=True).start()
    threading.Thread(target=weekly_loop, daemon=True).start()
    threading.Thread(target=extended_reports_loop, daemon=True).start()
    threading.Thread(target=optimizer_loop, daemon=True).start()
    threading.Thread(target=heatmap_loop, daemon=True).start()
    threading.Thread(target=htf_optimizer_loop, daemon=True).start()
