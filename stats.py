# stats.py (обновлённый с расширенными отчётами, системой защиты и улучшениями)

import os
from datetime import datetime, timedelta
from math import ceil

import matplotlib.pyplot as plt
import pandas as pd

from common.config_loader import (
    AGGRESSIVENESS_THRESHOLD,
    DAILY_PROFIT_TARGET,
    DAILY_TRADE_TARGET,
    EXPORT_PATH,
    LOG_LEVEL,
    TIMEZONE,
    WEEKLY_PROFIT_TARGET,
    trade_stats,
    trade_stats_lock,
)
from core.aggressiveness_controller import get_aggressiveness_score
from core.risk_utils import get_max_risk, set_max_risk
from core.volatility_controller import get_filter_relax_factor
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_core import get_cached_balance
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
        comment = "Bot was active, but no trades met entry conditions this period."
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

    # Подсчёт типов выходов из TP-лога
    exit_stats = ""
    try:
        import pandas as pd

        from common.config_loader import TP_LOG_FILE

        if os.path.exists(TP_LOG_FILE):
            df = pd.read_csv(TP_LOG_FILE)
            tp1 = len(df[df["Result"] == "TP1"])
            tp2 = len(df[df["Result"] == "TP2"])
            sl = len(df[df["Result"] == "SL"])
            soft = len(df[df["Result"] == "SOFT_EXIT"])
            switch = len(df[df["Result"] == "SWITCH_EXIT"])
            manual = len(df[df["Result"] == "MANUAL_EXIT"])
            trailing = len(df[df["Result"] == "TRAILING"])
            be = len(df[df["Result"] == "BE"])

            exit_stats = (
                f"\n🧩 *Exit Types:*\n"
                f"🏁 TP1: `{tp1}` | 🎯 TP2: `{tp2}` | ❌ SL: `{sl}`\n"
                f"🟡 Soft: `{soft}` | 🔄 Switch: `{switch}` | ✋ Manual: `{manual}` | 🔂 Trail: `{trailing}` | 🟢 BE: `{be}`"
            )
    except Exception as e:
        exit_stats = f"\n⚠️ *Exit stats unavailable:* {e}"

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
{exit_stats}
""".strip()

    return summary


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
    # Generate and send a graph for the weekly period
    generate_pnl_graph(days=7)
    if LOG_LEVEL == "DEBUG":
        log(f"Sent weekly report for {start}-{end.strftime('%d.%m')}.", level="DEBUG")


def send_monthly_report():
    end = now_with_timezone()
    start = (end - timedelta(days=30)).strftime("%d.%m")
    msg = build_performance_report("Monthly Performance Summary", f"{start}-{end.strftime('%d.%m')}")
    send_telegram_message(escape_markdown_v2(msg), force=True)
    # Generate and send a graph for the monthly period
    generate_pnl_graph(days=30)
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
    priority pair performance for small accounts, and performance by relax factor.

    Args:
        days (int): Period for analysis (default 1 day).
    """
    try:
        from common.config_loader import get_priority_small_balance_pairs
        from utils_core import get_cached_balance

        # Read data from tp_performance.csv
        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        if df.empty:
            report_message = "📊 Daily Report\nNo trades recorded yet."
            send_telegram_message(report_message, force=True, parse_mode="")
            return

        # Filter data for the last N days
        df = df[df["Date"] >= pd.Timestamp.now() - pd.Timedelta(days=days)]
        if df.empty:
            report_message = f"📊 Daily Report\nNo trades in the last {days} day(s)."
            send_telegram_message(report_message, force=True, parse_mode="")
            return

        # Get current balance
        balance = get_cached_balance()
        balance_category = "Small" if balance < 300 else "Medium" if balance < 600 else "Standard"

        # Total trades and winrate
        total_trades = len(df)
        win_trades = len(df[df["PnL (%)"] > 0])
        winrate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0
        total_pnl = df["PnL (%)"].sum()
        avg_pnl = df["PnL (%)"].mean() if total_trades > 0 else 0.0

        # Relax factor
        relax_factor = get_filter_relax_factor()

        # Base report
        report_message = (
            f"📊 Daily Report (Last {days} Day(s))\n"
            f"Account: {balance:.2f} USDC ({balance_category} Account)\n"
            f"Total Trades: {total_trades}\n"
            f"Winrate: {winrate:.2f}%\n"
            f"Total PnL: {total_pnl:.2f}%\n"
            f"Average PnL per Trade: {avg_pnl:.2f}%\n"
            f"Filter Relax Factor: {relax_factor:.2f}"
        )

        # Commission analysis
        if "Commission" in df.columns:
            total_commission = df["Commission"].sum()
            commission_pct = (total_commission / (balance * total_pnl / 100)) * 100 if total_pnl != 0 else 0
            report_message += "\n\n💰 Commission Analysis:\n"
            report_message += f"Total Commission: {total_commission:.6f} USDC\n"
            report_message += f"Commission Impact: {commission_pct:.2f}% of profit"

        # Absolute profit
        if "Absolute Profit" in df.columns:
            total_abs_profit = df["Absolute Profit"].sum()
            avg_profit_per_trade = total_abs_profit / total_trades if total_trades > 0 else 0
            report_message += "\n\n💵 Absolute Profit Analysis:\n"
            report_message += f"Total Profit: {total_abs_profit:.6f} USDC\n"
            report_message += f"Avg Profit/Trade: {avg_profit_per_trade:.6f} USDC"

        # Dynamic priority pair tracking
        if balance < 300:
            priority_pairs = get_priority_small_balance_pairs()
            priority_df = df[df["Symbol"].isin(priority_pairs)]
            if not priority_df.empty:
                priority_winrate = len(priority_df[priority_df["PnL (%)"] > 0]) / len(priority_df) * 100
                report_message += "\n\n🔍 Priority Pairs Performance:\n"
                report_message += f"Trades: {len(priority_df)}\n"
                report_message += f"Winrate: {priority_winrate:.2f}%"
                if "Absolute Profit" in priority_df.columns:
                    priority_profit = priority_df["Absolute Profit"].sum()
                    report_message += f"\nProfit: {priority_profit:.6f} USDC"
                    report_message += f"\n% of Total Profit: {(priority_profit / total_abs_profit) * 100:.2f}%" if total_abs_profit != 0 else ""
        # Add performance by relax factor (market regime analysis)
        if "Relax Factor" in df.columns:
            high_relax_df = df[df["Relax Factor"] > 0.8]
            low_relax_df = df[df["Relax Factor"] < 0.5]

            report_message += "\n\n📉 Performance by Market Regime:\n"
            if not high_relax_df.empty:
                high_relax_winrate = len(high_relax_df[high_relax_df["PnL (%)"] > 0]) / len(high_relax_df) * 100
                high_relax_pnl = high_relax_df["PnL (%)"].sum()
                report_message += "High Volatility (Relax > 0.8):\n"
                report_message += f"Trades: {len(high_relax_df)}\n"
                report_message += f"Winrate: {high_relax_winrate:.2f}%\n"
                report_message += f"PnL: {high_relax_pnl:.2f}%\n"
            else:
                report_message += "High Volatility (Relax > 0.8): No trades\n"

            if not low_relax_df.empty:
                low_relax_winrate = len(low_relax_df[low_relax_df["PnL (%)"] > 0]) / len(low_relax_df) * 100
                low_relax_pnl = low_relax_df["PnL (%)"].sum()
                report_message += "Low Volatility (Relax < 0.5):\n"
                report_message += f"Trades: {len(low_relax_df)}\n"
                report_message += f"Winrate: {low_relax_winrate:.2f}%\n"
                report_message += f"PnL: {low_relax_pnl:.2f}%\n"
            else:
                report_message += "Low Volatility (Relax < 0.5): No trades\n"

        # Add account growth information
        if "Absolute Profit" in df.columns:
            growth_pct = (total_abs_profit / balance) * 100
            daily_growth = growth_pct / days
            report_message += "\n📈 Account Growth:\n"
            report_message += f"Growth: {growth_pct:.2f}% over {days} day(s)\n"
            report_message += f"Daily Growth Rate: {daily_growth:.2f}%"

        send_telegram_message(report_message, force=True, parse_mode="")
        log(f"Daily report sent with {total_trades} trades", level="INFO")

    except Exception as e:
        log(f"[ERROR] Failed to generate daily report: {e}", level="ERROR")
        send_telegram_message(f"⚠️ Failed to generate daily report: {str(e)}", force=True, parse_mode="")


# ========== Performance Circuit Breaker and Trade Target Tracking ==========


def get_recent_trades(num_trades=20):
    """
    Get the most recent trades for performance analysis

    Args:
        num_trades (int): Number of most recent trades to analyze

    Returns:
        list: Trade records as dictionaries
    """
    try:
        if not os.path.exists(EXPORT_PATH):
            log(f"TP log file not found at: {EXPORT_PATH}", level="WARNING")
            return []

        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        # Sort by date (newest first) and take the most recent trades
        df = df.sort_values(by="Date", ascending=False).head(num_trades)
        return df.to_dict("records")
    except Exception as e:
        log(f"Error retrieving recent trades: {e}", level="ERROR")
        return []


def get_recent_performance_stats(num_trades=20):
    """
    Get performance statistics for the most recent trades

    Args:
        num_trades (int): Number of most recent trades to analyze

    Returns:
        dict: Performance statistics
    """
    trades = get_recent_trades(num_trades)

    # Default stats dictionary
    stats = {"num_trades": len(trades), "win_rate": 0.0, "profit_factor": 0.0, "avg_profit": 0.0, "profit_sum": 0.0, "loss_sum": 0.0, "wins": 0, "losses": 0}

    if not trades:
        return stats

    # Calculate wins, losses, and profit sums
    wins = sum(1 for t in trades if t.get("PnL (%)", 0) > 0)
    losses = sum(1 for t in trades if t.get("PnL (%)", 0) < 0)
    profit_sum = sum(t.get("PnL (%)", 0) for t in trades if t.get("PnL (%)", 0) > 0)
    loss_sum = abs(sum(t.get("PnL (%)", 0) for t in trades if t.get("PnL (%)", 0) < 0))

    # Calculate stats
    stats["win_rate"] = wins / len(trades) if len(trades) > 0 else 0.0
    stats["profit_factor"] = profit_sum / loss_sum if loss_sum > 0 else profit_sum if profit_sum > 0 else 0.0
    stats["avg_profit"] = sum(t.get("PnL (%)", 0) for t in trades) / len(trades) if len(trades) > 0 else 0.0
    stats["profit_sum"] = profit_sum
    stats["loss_sum"] = loss_sum
    stats["wins"] = wins
    stats["losses"] = losses

    return stats


def get_trades_for_today():
    """
    Get all trades for the current day

    Returns:
        list: Trade records for today
    """
    try:
        if not os.path.exists(EXPORT_PATH):
            return []

        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        today = pd.Timestamp.now().normalize()
        df_today = df[df["Date"].dt.normalize() == today]
        return df_today.to_dict("records")
    except Exception as e:
        log(f"Error retrieving today's trades: {e}", level="ERROR")
        return []


def get_trades_for_past_days(days=7):
    """
    Get all trades for the past N days

    Args:
        days (int): Number of past days to include

    Returns:
        list: Trade records for the specified period
    """
    try:
        if not os.path.exists(EXPORT_PATH):
            return []

        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        start_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=days)
        df_period = df[df["Date"].dt.normalize() >= start_date]
        return df_period.to_dict("records")
    except Exception as e:
        log(f"Error retrieving trades for past {days} days: {e}", level="ERROR")
        return []


def get_performance_stats():
    """
    Get overall performance statistics

    Returns:
        dict: Performance statistics
    """
    try:
        # Get all trades from log file
        if not os.path.exists(EXPORT_PATH):
            return {"win_rate": 0.0, "profit_factor": 0.0, "total_trades": 0, "wins": 0, "losses": 0}

        df = pd.read_csv(EXPORT_PATH)
        if df.empty:
            return {"win_rate": 0.0, "profit_factor": 0.0, "total_trades": 0, "wins": 0, "losses": 0}

        # Calculate wins, losses, and profit sums
        wins = len(df[df["PnL (%)"] > 0])
        losses = len(df[df["PnL (%)"] < 0])
        profit_sum = df[df["PnL (%)"] > 0]["PnL (%)"].sum()
        loss_sum = abs(df[df["PnL (%)"] < 0]["PnL (%)"].sum())

        # Calculate stats
        win_rate = wins / len(df) if len(df) > 0 else 0.0
        profit_factor = profit_sum / loss_sum if loss_sum > 0 else profit_sum if profit_sum > 0 else 0.0

        return {"win_rate": win_rate, "profit_factor": profit_factor, "total_trades": len(df), "wins": wins, "losses": losses}
    except Exception as e:
        log(f"Error calculating performance stats: {e}", level="ERROR")
        return {"win_rate": 0.0, "profit_factor": 0.0, "total_trades": 0, "wins": 0, "losses": 0}


def check_performance_circuit_breaker():
    """
    Monitors performance metrics and triggers protection if needed

    Returns:
        dict: Status information including any protective actions taken
    """
    # Get recent performance (last 20 trades)
    recent_stats = get_recent_performance_stats(20)

    if recent_stats["num_trades"] < 10:
        log("Insufficient data for performance circuit breaker (need at least 10 recent trades)", level="DEBUG")
        return {"status": "insufficient_data"}

    log(
        f"Performance circuit breaker: Win rate {recent_stats['win_rate']*100:.1f}%, PF {recent_stats['profit_factor']:.2f}, Wins {recent_stats['wins']}, Losses {recent_stats['losses']}",
        level="DEBUG",
    )

    # Check for poor performance conditions
    if recent_stats["win_rate"] < 0.50 and recent_stats["profit_factor"] < 1.0:
        # Poor performance detected - reduce risk by 40%
        current_max_risk = get_max_risk()
        new_max_risk = current_max_risk * 0.6
        set_max_risk(new_max_risk)

        message = (
            f"⚠️ PERFORMANCE ALERT: Win rate {recent_stats['win_rate']*100:.1f}%, PF {recent_stats['profit_factor']:.2f}.\n"
            f"Risk reduced to {new_max_risk*100:.1f}%. Please review strategy."
        )

        log(message, level="WARNING")
        send_telegram_message(message, force=True)

        return {"status": "protection_activated", "win_rate": recent_stats["win_rate"], "profit_factor": recent_stats["profit_factor"], "new_risk": new_max_risk}

    # Check for recovery condition to restore risk
    if recent_stats["win_rate"] > 0.60 and recent_stats["profit_factor"] > 1.5:
        current_max_risk = get_max_risk()
        # Assuming initial max risk is 0.03 (3%), restore to that level
        if current_max_risk < 0.03:
            set_max_risk(0.03)
            message = f"✅ PERFORMANCE RECOVERY: Win rate {recent_stats['win_rate']*100:.1f}%, PF {recent_stats['profit_factor']:.2f}.\n" f"Risk restored to 3.0%."
            log(message, level="INFO")
            send_telegram_message(message, force=True)
            return {"status": "risk_restored", "win_rate": recent_stats["win_rate"], "profit_factor": recent_stats["profit_factor"], "new_risk": 0.03}

    return {"status": "normal"}


def track_daily_trade_target():
    """
    Tracks progress toward daily trade target (8-11 trades)

    Returns:
        dict: Progress metrics and status information
    """
    # Get today's trades
    today_trades = get_trades_for_today()
    trades_count = len(today_trades)

    # Calculate today's profit
    today_profit = 0.0
    if today_trades and "Absolute Profit" in today_trades[0]:
        # Use absolute profit if available
        today_profit = sum(trade.get("Absolute Profit", 0) for trade in today_trades)
    else:
        # Estimate from PnL percentage and balance at entry
        today_profit = 0.0
        for trade in today_trades:
            balance_at_entry = trade.get("Balance at Entry", get_cached_balance())
            pnl_percent = trade.get("PnL (%)", 0)
            trade_profit = (pnl_percent / 100) * balance_at_entry
            today_profit += trade_profit

    # Get weekly stats
    weekly_trades = get_trades_for_past_days(7)
    weekly_profit = 0.0
    if weekly_trades and "Absolute Profit" in weekly_trades[0]:
        weekly_profit = sum(trade.get("Absolute Profit", 0) for trade in weekly_trades)
    else:
        weekly_profit = 0.0
        for trade in weekly_trades:
            balance_at_entry = trade.get("Balance at Entry", get_cached_balance())
            pnl_percent = trade.get("PnL (%)", 0)
            trade_profit = (pnl_percent / 100) * balance_at_entry
            weekly_profit += trade_profit

    # Calculate progress percentages
    daily_trade_progress = (trades_count / DAILY_TRADE_TARGET) * 100 if DAILY_TRADE_TARGET > 0 else 0
    daily_profit_progress = (today_profit / DAILY_PROFIT_TARGET) * 100 if DAILY_PROFIT_TARGET > 0 else 0
    weekly_profit_progress = (weekly_profit / WEEKLY_PROFIT_TARGET) * 100 if WEEKLY_PROFIT_TARGET > 0 else 0

    # Notify if daily profit target is reached
    if today_profit >= DAILY_PROFIT_TARGET:
        message = f"✅ Daily profit target reached! Achieved ${today_profit:.2f} of ${DAILY_PROFIT_TARGET:.2f}."
        log(message, level="INFO")
        send_telegram_message(message, force=True)

    # Alert if trade count is too low relative to time of day
    current_hour = datetime.now().hour
    trading_hours_elapsed = max(1, min(current_hour - 9, 12))  # Assume 9AM-9PM trading day
    expected_trades_by_now = (trading_hours_elapsed / 12) * DAILY_TRADE_TARGET

    if trades_count < expected_trades_by_now * 0.7 and current_hour >= 12:
        message = f"⚠️ TRADE ALERT: Only {trades_count} trades so far today. Need {DAILY_TRADE_TARGET - trades_count} more to reach target."
        log(message, level="WARNING")
        send_telegram_message(message, force=True)

    # Log daily progress
    log(
        f"Daily target progress: {trades_count}/{DAILY_TRADE_TARGET} trades ({daily_trade_progress:.1f}%), "
        f"${today_profit:.2f}/${DAILY_PROFIT_TARGET:.2f} profit ({daily_profit_progress:.1f}%)",
        level="INFO",
    )

    return {
        "trades_today": trades_count,
        "target_trades": DAILY_TRADE_TARGET,
        "daily_profit": today_profit,
        "daily_profit_target": DAILY_PROFIT_TARGET,
        "weekly_profit": weekly_profit,
        "weekly_profit_target": WEEKLY_PROFIT_TARGET,
        "daily_trade_progress": daily_trade_progress,
        "daily_profit_progress": daily_profit_progress,
        "weekly_profit_progress": weekly_profit_progress,
    }


def handle_goal_command(params=None):
    """
    Show progress toward daily and weekly goals

    Args:
        params (list, optional): Command parameters

    Returns:
        str: Formatted message with goal progress information
    """
    metrics = track_daily_trade_target()

    message = (
        f"📊 *Goal Progress*\n\n"
        f"Today's Trades: {metrics['trades_today']}/{metrics['target_trades']} ({metrics['daily_trade_progress']:.1f}%)\n"
        f"Today's Profit: ${metrics['daily_profit']:.2f}/${metrics['daily_profit_target']:.2f} ({metrics['daily_profit_progress']:.1f}%)\n\n"
        f"Weekly Profit: ${metrics['weekly_profit']:.2f}/${metrics['weekly_profit_target']:.2f} ({metrics['weekly_profit_progress']:.1f}%)\n"
    )

    # Add average profit per trade
    if metrics["trades_today"] > 0:
        avg_profit = metrics["daily_profit"] / metrics["trades_today"]
        trades_needed = ceil((metrics["daily_profit_target"] - metrics["daily_profit"]) / avg_profit) if avg_profit > 0 else "N/A"

        message += "\n📈 Stats:\n"
        message += f"Avg Profit/Trade: ${avg_profit:.2f}\n"

        if trades_needed != "N/A":
            message += f"Est. Trades Needed: {trades_needed} more\n"

    return message
