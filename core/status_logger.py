# core/status_logger.py
from datetime import datetime
from statistics import mean

from telegram_utils import send_telegram_message

from utils_core import get_runtime_config
from utils_logging import log


def build_status_report():
    config = get_runtime_config()
    active_symbols = config.get("active_symbols", [])
    last_score_data = config.get("last_score_data", {})
    blocked_symbols = config.get("blocked_symbols", {})
    missed = config.get("missed_opportunities", {})
    open_positions = config.get("open_positions", {})

    symbol_count = len(active_symbols)
    blocked_count = len(blocked_symbols)
    missed_count = len(missed)

    recent_checked = len(last_score_data)
    recent_signals = sum(1 for d in last_score_data.values() if d.get("final", False))
    rejected = recent_checked - recent_signals

    scores = [d.get("total") for d in last_score_data.values() if "total" in d]
    avg_score = round(mean(scores), 2) if scores else "-"
    max_score = round(max(scores), 2) if scores else "-"
    min_score = round(min(scores), 2) if scores else "-"

    trades_open = len(open_positions)
    trades_tp1 = sum(1 for v in open_positions.values() if v.get("tp1_hit"))
    trades_sl = sum(1 for v in open_positions.values() if v.get("stopped_by") == "sl")

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"[Status] {now}\n"
        f"• Active: {symbol_count} | Blocked: {blocked_count} | Missed: {missed_count}\n"
        f"• Last Check → {recent_checked} scanned | {recent_signals} valid | {rejected} rejected\n"
        f"• Score Activity: {avg_score} avg | Min: {min_score} | Max: {max_score}\n"
        f"• Trades Open: {trades_open} | TP1 Hit: {trades_tp1} | SL Hit: {trades_sl}"
    )


def log_symbol_activity_status():
    try:
        report = build_status_report()
        log(report, level="INFO")
    except Exception as e:
        log(f"[StatusLogger] Error generating report: {e}", level="ERROR")


def log_symbol_activity_status_to_telegram():
    try:
        report = build_status_report()
        send_telegram_message(f"*{report}*", markdown=True)
    except Exception as e:
        send_telegram_message(f"[StatusLogger Error] Failed to send status: {e}")
