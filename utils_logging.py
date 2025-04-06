import os
import shutil
from datetime import datetime

from colorama import Fore, Style, init
from filelock import FileLock

from config import DRY_RUN, LOG_FILE_PATH, LOG_LEVEL  # Removed TIMEZONE
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message

init(autoreset=True)

MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

LOG_COLORS = {
    "DEBUG": Fore.CYAN,
    "INFO": Fore.WHITE,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
}


def notify_error(msg):
    """Notify an error via Telegram."""
    send_telegram_message(f"❌ {escape_markdown_v2(str(msg))}", force=True)


def log(message: str, important=False, level="INFO"):
    message_level = LOG_LEVELS.get(level, LOG_LEVELS["INFO"])
    min_level = LOG_LEVELS.get(LOG_LEVEL, LOG_LEVELS["INFO"])
    if message_level < min_level:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [{level}] {message}"

    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    lock = FileLock(f"{LOG_FILE_PATH}.lock")
    try:
        with lock:
            if os.path.exists(LOG_FILE_PATH) and os.path.getsize(LOG_FILE_PATH) > MAX_LOG_SIZE:
                for i in range(BACKUP_COUNT - 1, 0, -1):
                    old_file = f"{LOG_FILE_PATH}.{i}"
                    new_file = f"{LOG_FILE_PATH}.{i + 1}"
                    if os.path.exists(old_file):
                        os.rename(old_file, new_file)
                if os.path.exists(LOG_FILE_PATH):
                    os.rename(LOG_FILE_PATH, f"{LOG_FILE_PATH}.1")
                with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write("--- Telegram Log ---\n")

            if not os.path.exists(LOG_FILE_PATH):
                with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write("--- Telegram Log ---\n")

            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(full_msg + "\n")
    except Exception as e:
        error_msg = f"[ERROR] Failed to write to log file {LOG_FILE_PATH}: {e}"
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        print(f"{Fore.RED}{full_msg}{Style.RESET_ALL}")
        print()

    if important or DRY_RUN or message_level >= LOG_LEVELS["WARNING"]:
        color = LOG_COLORS.get(level, Fore.WHITE)
        print(f"{color}{full_msg}{Style.RESET_ALL}")
        print()


def get_recent_logs(n=50):
    """Get the last n lines from the log file."""
    if not os.path.exists(LOG_FILE_PATH):
        log(f"Log file {LOG_FILE_PATH} not found.", level="WARNING")
        return "Log file not found."
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


def log_dry_entry(entry_data):
    """Log a dry run entry."""
    log(f"Dry entry log: {entry_data}", important=False, level="INFO")


def now():
    """Get the current time in the configured timezone."""
    return datetime.now()


def backup_config():
    """Backup the config.py file."""
    backup_dir = "data/backups"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_file = f"{backup_dir}/config_{timestamp}.py"
        shutil.copy("config.py", backup_file)
        send_telegram_message(
            f"📂 Config backup saved as {escape_markdown_v2(os.path.basename(backup_file))}",
            force=True,
        )
        log(f"Backed up config to {backup_file}", level="INFO")
    except Exception as e:
        log(f"Error backing up config: {e}", level="ERROR")
        send_telegram_message(f"❌ Error backing up config: {str(e)}", force=True)


def restore_config(backup_file=None):
    """Restore the config.py file from a backup."""
    backup_dir = "data/backups"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if not backups:
            send_telegram_message("❌ No backups found", force=True)
            log("No config backups found.", level="WARNING")
            return
        if not backup_file:
            backup_file = backups[0]
        shutil.copy(f"{backup_dir}/{backup_file}", "config.py")
        send_telegram_message(
            f"🔄 Restored config from {escape_markdown_v2(backup_file)}", force=True
        )
        log(f"Restored config from {backup_file}", level="INFO")
        if len(backups) > 5:
            for old in backups[5:]:
                os.remove(f"{backup_dir}/{old}")
            log("Cleaned up old backups, kept latest 5.", level="INFO")
    except Exception as e:
        log(f"Error restoring config: {e}", level="ERROR")
        send_telegram_message(f"❌ Error restoring config: {str(e)}", force=True)


def notify_ip_change(old_ip, new_ip, timestamp, forced_stop=False):
    from ip_monitor import router_reboot_mode

    try:
        message = (
            f"⚠️ *IP Address Changed!*\n\n"
            f"🕒 `{timestamp} (Bratislava)`\n"
            f"🌐 Old IP: `{old_ip}`\n"
            f"🌐 New IP: `{new_ip}`\n"
        )
        if router_reboot_mode.get("enabled"):
            message += "\n\n✅ No action needed. IP changed while reboot mode is active (30 min safe window)."
        elif forced_stop:
            message += (
                "\n\n🚫 *Bot will stop after closing open orders.*\n"
                "You can cancel this with `/cancel_stop`."
            )
        send_telegram_message(message, force=True)
        log(f"IP changed from {old_ip} to {new_ip}", level="WARNING")
    except Exception as e:
        log(f"[notify_ip_change] Telegram error: {e}", level="ERROR")
