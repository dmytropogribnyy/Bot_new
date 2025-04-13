import json

from config import DRY_RUN, FIXED_PAIRS
from core.trade_engine import close_dry_trade
from ip_monitor import (
    cancel_router_reboot_mode,
    enable_router_reboot_mode,
    force_ip_check_now,
    get_ip_status_message,
)
from stats import send_daily_report
from telegram.telegram_utils import send_telegram_message
from utils_logging import get_recent_logs, log


def handle_ip_and_misc_commands(text, handle_stop):
    """Handle IP-related, pair-related, and miscellaneous Telegram commands."""
    if text == "/router_reboot":
        enable_router_reboot_mode()
        log("Router reboot mode enabled via /router_reboot command.", level="INFO")

    elif text == "/cancel_reboot":
        cancel_router_reboot_mode()
        log("Router reboot mode cancelled via /cancel_reboot command.", level="INFO")

    elif text == "/ipstatus":
        msg = get_ip_status_message()
        send_telegram_message(msg, force=True, parse_mode="")
        log("Fetched IP status via /ipstatus command.", level="INFO")

    elif text == "/forceipcheck":
        force_ip_check_now(handle_stop)
        log("Forced IP check via /forceipcheck command.", level="INFO")

    elif text == "/pairstoday":
        try:
            with open("data/dynamic_symbols.json", "r") as f:
                pairs = json.load(f)
            fixed = [p for p in pairs if p in FIXED_PAIRS]
            dynamic = [p for p in pairs if p not in FIXED_PAIRS]
            msg = (
                f"Active Pairs Today: {len(pairs)}\n\n"
                f"Fixed: {', '.join([p.split('/')[0] for p in fixed])}\n"
                f"Dynamic: {', '.join([p.split('/')[0] for p in dynamic])}"
            )
            send_telegram_message(msg, force=True, parse_mode="")
            log("Fetched active pairs via /pairstoday command.", level="INFO")
        except Exception as e:
            error_msg = f"Failed to load symbol list: {str(e)}"
            send_telegram_message(error_msg, force=True, parse_mode="")
            log(error_msg, level="ERROR")

    elif text.startswith("/close_dry"):
        if DRY_RUN:
            try:
                symbol = text.split()[1] if len(text.split()) > 1 else "BTC/USDC"
                close_dry_trade(symbol)
                send_telegram_message(
                    f"Closed DRY position for {symbol}", force=True, parse_mode=""
                )
            except Exception as e:
                send_telegram_message(f"Error closing DRY position: {e}", force=True, parse_mode="")

    elif text == "/debuglog":
        if DRY_RUN:
            logs = get_recent_logs()
            msg = f"Debug Log (last {len(logs.splitlines())} lines):\n\n{logs[:4000]}"
            send_telegram_message(msg, force=True, parse_mode="")
            log("Sent debug log via /debuglog command.", level="INFO")
        else:
            send_telegram_message(
                "Debug log only available in DRY_RUN mode.", force=True, parse_mode=""
            )
            log("Debug log request denied: not in DRY_RUN mode.", level="INFO")

    elif text == "/log":
        send_daily_report()
        log("Sent daily report via /log command.", level="INFO")
