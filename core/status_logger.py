# status_logger.py

from datetime import datetime

from telegram.telegram_utils import send_telegram_message
from utils_core import get_runtime_config
from utils_logging import log


def build_status_report():
    """
    Build a simple status report reflecting current active symbols from runtime_config.
    (Removed old references to 'score', 'blocked_symbols', 'missed_opportunities', etc.)
    """
    config = get_runtime_config()
    active_symbols = config.get("active_symbols", [])  # or any other relevant list
    symbol_count = len(active_symbols)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    return f"[Status] {now}\n" f"• Active Symbols: {symbol_count}\n" f"• {', '.join(active_symbols) if active_symbols else 'No symbols'}"


def log_symbol_activity_status():
    """
    Log status report to main.log
    """
    try:
        report = build_status_report()
        log(report, level="INFO")
    except Exception as e:
        log(f"[StatusLogger] Error generating report: {e}", level="ERROR")


def log_symbol_activity_status_to_telegram():
    """
    Send status report to Telegram
    """
    try:
        report = build_status_report()
        send_telegram_message(f"*{report}*", markdown=True)
    except Exception as e:
        send_telegram_message(f"[StatusLogger Error] Failed to send status: {e}")
