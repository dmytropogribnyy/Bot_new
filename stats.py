# stats.py (обновлённый с расширенными отчётами)

import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd

from common.config_loader import (
    AGGRESSIVENESS_THRESHOLD,
    EXPORT_PATH,
    LOG_LEVEL,
    TIMEZONE,
    trade_stats,
    trade_stats_lock,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.volatility_controller import get_filter_relax_factor
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log


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
    streak_str = f"{abs(stats['streak_loss'])} wins" if stats["streak_loss"] < 0 else (f"{stats['streak_loss']} losses" if stats["streak_loss"] > 0 else "-")
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
            f.write(f"[{timestamp}] Total: {stats['total']}, Wins: {stats['wins']}, " f"Losses: {stats['losses']}, PnL: {stats['pnl']}, Withdrawals: {stats['withdrawals']}\n")
        send_telegram_message(escape_markdown_v2("Trade log exported."), force=True)
        if LOG_LEVEL == "DEBUG":
            log("Trade log exported successfully.", level="DEBUG")
    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"Failed to export trade log: {e}"), force=True)
        log(f"Failed to export trade log: {e}", level="ERROR")


def send_daily_report(parse_mode="MarkdownV2"):
    """Send a daily performance report via Telegram.

    Args:
        parse_mode (str): Telegram parse mode ("MarkdownV2", "HTML", or "" for plain text)
    """
    today = now_with_timezone().strftime("%d.%m.%Y")
    msg = build_performance_report("Daily Performance Summary", today)

    # Only escape if using MarkdownV2
    if parse_mode == "MarkdownV2":
        msg = escape_markdown_v2(msg)

    send_telegram_message(msg, force=True, parse_mode=parse_mode)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent daily report for {today}.", level="DEBUG")


def send_weekly_report(parse_mode="MarkdownV2"):
    end = now_with_timezone()
    start = (end - timedelta(days=7)).strftime("%d.%m")
    msg = build_performance_report("Weekly Performance Summary", f"{start}-{end.strftime('%d.%m')}")

    if parse_mode == "MarkdownV2":
        msg = escape_markdown_v2(msg)

    send_telegram_message(msg, force=True, parse_mode=parse_mode)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent weekly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_monthly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=30)).strftime("%d.%m")
    msg = build_performance_report("Monthly Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent monthly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_quarterly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=90)).strftime("%d.%m")
    msg = build_performance_report("3-Month Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent quarterly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_halfyear_report():
    end = now_with_timezone()
    start = (end - timedelta(days=180)).strftime("%d.%m")
    msg = build_performance_report("6-Month Performance Summary", f"{start}-{end.strftime('%d.%m')}")
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


def generate_pnl_graph(days=7):
    df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
    df = df[df["Date"] >= datetime.now() - timedelta(days=days)]
    if df.empty:
        return
    df["Cumulative PnL"] = df["PnL (%)"].cumsum()
    plt.figure(figsize=(10, 6))
    plt.plot(df["Date"], df["Cumulative PnL"], label="Cumulative PnL (%)")
    plt.title(f"PnL Over Last {days} Days")
    plt.xlabel("Date")
    plt.ylabel("Cumulative PnL (%)")
    plt.legend()
    plt.grid()
    plt.savefig("data/pnl_graph.png")
    plt.close()
    send_telegram_message("data/pnl_graph.png", caption=f"PnL Graph ({days}d)")
    log("PnL graph sent", level="INFO")


def generate_daily_report(days=1):
    """
    Generates a daily report and sends it to Telegram.
    Includes trade statistics, winrate, PnL, commission impact,
    and priority pair performance for small accounts.

    Args:
        days (int): Period for analysis (default 1 day).
    """
    try:
        from utils_core import get_cached_balance

        # Read data from tp_performance.csv
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        if df.empty:
            report_message = "📊 Daily Report\n" "No trades recorded yet."
            send_telegram_message(report_message, force=True, parse_mode="")
            return

        # Filter data for the last days days
        df = df[df["Date"] >= pd.Timestamp.now() - pd.Timedelta(days=days)]
        if df.empty:
            report_message = f"📊 Daily Report\n" f"No trades in the last {days} day(s)."
            send_telegram_message(report_message, force=True, parse_mode="")
            return

        # Get current balance for context
        balance = get_cached_balance()
        balance_category = "Small" if balance < 150 else "Medium" if balance < 300 else "Standard"

        # Total number of trades
        total_trades = len(df)

        # Winning trades count (TP1, TP2, SOFT_EXIT with profit)
        win_trades = len(df[df["Result"].isin(["TP1", "TP2"])])
        if "Net PnL (%)" in df.columns:
            # If we have net PnL column, use that for more accurate win counting
            win_trades = len(df[df["Net PnL (%)"] > 0])

        winrate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Total PnL
        total_pnl = df["PnL (%)"].sum()

        # Average PnL per trade
        avg_pnl = df["PnL (%)"].mean() if total_trades > 0 else 0.0

        # Get relax_factor
        relax_factor = get_filter_relax_factor()

        # Form base report
        report_message = (
            f"📊 Daily Report (Last {days} Day(s))\n"
            f"Account: {balance:.2f} USDC ({balance_category} Account)\n"
            f"Total Trades: {total_trades}\n"
            f"Winrate: {winrate:.2f}%\n"
            f"Total PnL: {total_pnl:.2f}%\n"
            f"Average PnL per Trade: {avg_pnl:.2f}%\n"
            f"Filter Relax Factor: {relax_factor:.2f}"
        )

        # Add commission impact analysis (critical for small accounts)
        if "Commission" in df.columns:
            total_commission = df["Commission"].sum()
            commission_pct = (total_commission / (balance * total_pnl / 100)) * 100 if total_pnl != 0 else 0
            report_message += "\n\n💰 Commission Analysis:\n"
            report_message += f"Total Commission: {total_commission:.6f} USDC\n"
            report_message += f"Commission Impact: {commission_pct:.2f}% of profit"

        # Add absolute profit tracking (especially important for small accounts)
        if "Absolute Profit" in df.columns:
            total_abs_profit = df["Absolute Profit"].sum()
            avg_profit_per_trade = total_abs_profit / total_trades if total_trades > 0 else 0
            report_message += "\n\n💵 Absolute Profit Analysis:\n"
            report_message += f"Total Profit: {total_abs_profit:.6f} USDC\n"
            report_message += f"Avg Profit/Trade: {avg_profit_per_trade:.6f} USDC"

        # Add priority pair tracking for small accounts
        if balance < 150:  # For small accounts
            priority_pairs = ["XRP/USDC", "DOGE/USDC", "ADA/USDC", "SOL/USDC"]
            priority_df = df[df["Symbol"].isin(priority_pairs)]
            if not priority_df.empty:
                priority_winrate = len(priority_df[priority_df["Result"].isin(["TP1", "TP2"])]) / len(priority_df) * 100
                report_message += "\n\n🔍 Priority Pairs Performance:\n"
                report_message += f"Trades: {len(priority_df)}\n"
                report_message += f"Winrate: {priority_winrate:.2f}%"
                if "Absolute Profit" in priority_df.columns:
                    priority_profit = priority_df["Absolute Profit"].sum()
                    report_message += f"\nProfit: {priority_profit:.6f} USDC"
                    report_message += f"\n% of Total Profit: {(priority_profit/total_abs_profit)*100:.2f}%" if total_abs_profit != 0 else ""

        # Add account growth information
        if "Absolute Profit" in df.columns:
            growth_pct = (total_abs_profit / balance) * 100
            daily_growth = growth_pct / days
            report_message += "\n\n📈 Account Growth:\n"
            report_message += f"Growth: {growth_pct:.2f}% over {days} day(s)\n"
            report_message += f"Daily Growth Rate: {daily_growth:.2f}%"

        send_telegram_message(report_message, force=True, parse_mode="")
        log(f"Daily report sent with {total_trades} trades", level="INFO")

    except Exception as e:
        log(f"[ERROR] Failed to generate daily report: {e}", level="ERROR")
        send_telegram_message(f"⚠️ Failed to generate daily report: {str(e)}", force=True, parse_mode="")
