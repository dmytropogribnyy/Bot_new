import os
import json
import shutil
import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, LOG_FILE_PATH, TIMEZONE, DRY_RUN


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2, preserving emojis and formatting."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join("\\" + char if char in escape_chars else char for char in str(text))


def send_telegram_message(text: str, force=False):
    """Send a message to Telegram with MarkdownV2 support."""
    print(f"📤 [utils.py] Sending to Telegram: {text[:60]}...")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Truncate message if too long (Telegram limit: 4096 characters)
    if len(text) > 4096:
        text = text[:4090] + "..."
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_notification": not force,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ [utils.py] Message sent successfully: {text[:60]}...")
        else:
            print(f"⚠️ Telegram response {response.status_code}: {response.text}")
            if force:
                # Fallback to plain text
                payload["parse_mode"] = ""
                requests.post(url, json=payload, timeout=10)
                print(f"⚠️ Sent as plain text (forced): {text[:60]}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")
        if force:
            # Fallback to plain text
            payload["parse_mode"] = ""
            requests.post(url, json=payload, timeout=10)
            print(f"⚠️ Sent as plain text (forced): {text[:60]}")


def send_telegram_file(file_path: str, caption: str = ""):
    if TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None:
        return
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                data=data,
                files=files,
                timeout=15,
            )
    except:
        print(f"[Telegram FILE FAIL] {file_path}")


def notify_error(msg):
    send_telegram_message(f"❌ {escape_markdown_v2(str(msg))}", force=True)


def log(message: str, important=False):
    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {message}"
    # Ensure the log file exists and add a header if it's new
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("--- Telegram Log ---\n")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")
    if important or DRY_RUN:
        print(full_msg)


def get_recent_logs(n=50):
    if not os.path.exists(LOG_FILE_PATH):
        return "Log file not found."
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


def get_last_signal_time():
    path = "data/last_signal.txt"
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        ts = f.read().strip()
        return datetime.fromisoformat(ts)


def update_last_signal_time():
    path = "data/last_signal.txt"
    with open(path, "w") as f:
        f.write(datetime.now().isoformat())


def get_open_symbols():
    from config import exchange

    try:
        open_syms = []
        positions = exchange.fetch_positions()
        for p in positions:
            if float(p.get("contracts", 0)) > 0:
                open_syms.append(p["symbol"])
        return open_syms
    except:
        return []


def backup_config():
    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_file = f"{backup_dir}/config_{timestamp}.py"
    shutil.copy("config.py", backup_file)
    send_telegram_message(
        f"📂 Config backup saved as {escape_markdown_v2(os.path.basename(backup_file))}",
        force=True,
    )


def restore_config(backup_file=None):
    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)
    backups = sorted(os.listdir(backup_dir), reverse=True)
    if not backups:
        send_telegram_message("❌ No backups found", force=True)
        return
    if not backup_file:
        backup_file = backups[0]
    shutil.copy(f"{backup_dir}/{backup_file}", "config.py")
    send_telegram_message(
        f"🔄 Restored config from {escape_markdown_v2(backup_file)}", force=True
    )
    if len(backups) > 5:
        for old in backups[5:]:
            os.remove(f"{backup_dir}/{old}")


def now():
    return datetime.now(TIMEZONE)


def log_dry_entry(entry_data):
    log(f"Dry entry log: {entry_data}", important=False)
