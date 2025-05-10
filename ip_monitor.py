# ip_monitor.py
import os
import time
from datetime import datetime, timedelta

import requests

from common.config_loader import (
    DRY_RUN,
    IP_MONITOR_INTERVAL_SECONDS,
    ROUTER_REBOOT_MODE_TIMEOUT_MINUTES,
)
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message
from utils_logging import log

IP_STATUS_FILE = "data/last_ip.txt"
router_reboot_mode = {"enabled": False, "expires_at": None}
last_ip_check_time = None
boot_time = time.time()


def get_current_ip():
    try:
        ip = requests.get("https://api.ipify.org").text.strip()
        log(f"Fetched current IP: {ip}", level="INFO")
        return ip
    except Exception as e:
        log(f"Error fetching IP: {e}", level="ERROR")
        return None


def read_last_ip():
    try:
        with open(IP_STATUS_FILE, "r") as f:
            ip = f.read().strip()
            log(f"Read last IP: {ip}", level="DEBUG")
            return ip
    except FileNotFoundError:
        log(f"IP status file {IP_STATUS_FILE} not found.", level="INFO")
        return None
    except Exception as e:
        log(f"Error reading IP status file {IP_STATUS_FILE}: {e}", level="ERROR")
        return None


def write_last_ip(ip):
    try:
        os.makedirs(os.path.dirname(IP_STATUS_FILE), exist_ok=True)
        with open(IP_STATUS_FILE, "w") as f:
            f.write(ip)
        log(f"Wrote IP {ip} to {IP_STATUS_FILE}", level="INFO")
    except Exception as e:
        log(f"Error writing IP to {IP_STATUS_FILE}: {e}", level="ERROR")


def check_ip_change(stop_callback):
    global last_ip_check_time
    current_ip = get_current_ip()
    last_ip = read_last_ip()
    last_ip_check_time = datetime.now()

    if current_ip and current_ip != last_ip:
        write_last_ip(current_ip)
        now = datetime.now().strftime("%d %b %Y, %H:%M")

        if router_reboot_mode["enabled"]:
            msg = "⚠️ IP Address Changed\n" f"🕒 Time: {now} (Bratislava)\n" f"🌐 Old IP: {last_ip}\n" f"🌐 New IP: {current_ip}\n" "✅ No action needed (reboot mode active)."
        elif time.time() - boot_time <= 300:
            msg = "⚠️ IP Address Changed\n" f"🕒 Time: {now} (Bratislava)\n" f"🌐 Old IP: {last_ip}\n" f"🌐 New IP: {current_ip}\n" "ℹ️ Ignored due to recent startup (within 5 minutes)."
            log("[IP Monitor] IP changed, but within 5 minutes of startup — ignoring", level="INFO")
        else:
            msg = (
                "⚠️ IP Address Changed\n"
                f"🕒 Time: {now} (Bratislava)\n"
                f"🌐 Old IP: {last_ip}\n"
                f"🌐 New IP: {current_ip}\n"
                "🚫 Bot will stop after closing orders.\n"
                f"ℹ️ Update Binance API IP whitelist with {current_ip}, then use /resume_after_ip."
            )
            if stop_callback:
                log("IP changed, calling stop callback.", level="WARNING")
                stop_callback()

        send_telegram_message(msg, force=True, parse_mode="")
        return True, current_ip, last_ip, now

    return False, current_ip, last_ip, None


def enable_router_reboot_mode():
    router_reboot_mode["enabled"] = True
    router_reboot_mode["expires_at"] = datetime.now() + timedelta(minutes=ROUTER_REBOOT_MODE_TIMEOUT_MINUTES)
    send_telegram_message(
        escape_markdown_v2(f"🟢 Router reboot mode ENABLED for {ROUTER_REBOOT_MODE_TIMEOUT_MINUTES} minutes."),
        force=True,
    )
    expires_at = router_reboot_mode["expires_at"].strftime("%H:%M")
    log(
        f"Router reboot mode enabled for {ROUTER_REBOOT_MODE_TIMEOUT_MINUTES} minutes. Expires at {expires_at} (Bratislava).",
        level="INFO",
    )


def cancel_router_reboot_mode():
    router_reboot_mode["enabled"] = False
    router_reboot_mode["expires_at"] = None
    send_telegram_message(
        escape_markdown_v2("🔵 Router reboot mode CANCELLED.\nReboot mode deactivated early."),
        force=True,
    )
    log("Router reboot mode cancelled.", level="INFO")


def check_reboot_mode_expiration():
    if router_reboot_mode["enabled"] and datetime.now() > router_reboot_mode["expires_at"]:
        log("Router reboot mode expired, cancelling.", level="INFO")
        cancel_router_reboot_mode()


def get_ip_status_message():
    current_ip = get_current_ip() or "Unknown"
    last_ip = read_last_ip() or "Unknown"
    last_check = last_ip_check_time.strftime("%d %b %Y, %H:%M") if last_ip_check_time else "N/A"
    reboot_status = "🟢 ENABLED" if router_reboot_mode["enabled"] else "Disabled"

    if router_reboot_mode["enabled"] and router_reboot_mode["expires_at"]:
        remaining_minutes = max(
            0,
            int((router_reboot_mode["expires_at"] - datetime.now()).total_seconds() / 60),
        )
        expires_time = router_reboot_mode["expires_at"].strftime("%H:%M")
        expires_info = f"{remaining_minutes} min left, until {expires_time} Bratislava"
    else:
        expires_info = "N/A"

    msg = (
        "🛰 IP Monitoring Status\n"
        f"🌐 Current IP: {current_ip}\n"
        f"📡 Previous IP: {last_ip}\n"
        f"📅 Last check: {last_check} (Bratislava)\n"
        f"⚙️ Router Reboot Mode: {reboot_status} ({expires_info})"
    )
    return msg


def force_ip_check_now(stop_callback):
    log("Forced IP check requested.", level="INFO")
    changed, current_ip, last_ip, change_time = check_ip_change(stop_callback)

    last_check = last_ip_check_time.strftime("%d %b %Y, %H:%M") if last_ip_check_time else "N/A"
    reboot_status = "🟢 ENABLED" if router_reboot_mode["enabled"] else "Disabled"

    if router_reboot_mode["enabled"] and router_reboot_mode["expires_at"]:
        remaining_minutes = max(
            0,
            int((router_reboot_mode["expires_at"] - datetime.now()).total_seconds() / 60),
        )
        expires_time = router_reboot_mode["expires_at"].strftime("%H:%M")
        expires_info = f"{remaining_minutes} min left, until {expires_time} Bratislava"
    else:
        expires_info = "N/A"

    if changed:
        result_msg = "⚠️ IP has changed!"
        if router_reboot_mode["enabled"]:
            result_msg += "\n✅ No action needed (reboot mode active)."
        elif time.time() - boot_time <= 300:
            result_msg += "\nℹ️ Ignored due to recent startup."
        else:
            result_msg += "\n🚫 Bot will stop after closing orders.\n" f"ℹ️ Update Binance API IP whitelist with {current_ip or 'Unknown'}, then use /resume_after_ip."
    else:
        result_msg = "✅ No changes detected."

    msg = (
        "🛰 Forced IP Check Result\n"
        f"🌐 Current IP: {current_ip or 'Unknown'}\n"
        f"📡 Previous IP: {last_ip or 'Unknown'}\n"
        f"🕒 Time: {change_time or last_check} (Bratislava)\n"
        f"⚙️ Router Reboot Mode: {reboot_status} ({expires_info})\n"
        f"{result_msg}"
    )
    send_telegram_message(msg, force=True, parse_mode="")


def start_ip_monitor(stop_callback, interval_seconds=IP_MONITOR_INTERVAL_SECONDS):
    global last_ip_check_time
    last_ip_check_time = datetime.now()
    log(
        f"Starting IP monitor with interval {interval_seconds} seconds in reboot mode, 30 minutes otherwise.",
        level="INFO",
    )
    while True:
        check_reboot_mode_expiration()
        if router_reboot_mode["enabled"]:
            check_ip_change(stop_callback)
            time.sleep(interval_seconds)
        else:
            time_since_last_check = (datetime.now() - last_ip_check_time).total_seconds()
            check_interval = 120 if DRY_RUN else 1800  # 2 min (DRY), 30 min (REAL)
            if time_since_last_check >= check_interval:
                check_ip_change(stop_callback)
                last_ip_check_time = datetime.now()
            time.sleep(60)
