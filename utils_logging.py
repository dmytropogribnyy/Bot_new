from contextlib import contextmanager
from datetime import datetime
import os
import shutil

from colorama import Fore, Style, init
from filelock import FileLock

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

_error_state = {"in_handling": False}


@contextmanager
def error_handling_guard():
    if _error_state["in_handling"]:
        yield False
    else:
        _error_state["in_handling"] = True
        try:
            yield True
        finally:
            _error_state["in_handling"] = False


def notify_error(msg):
    try:
        print(f"\nERROR: {msg}\n")
    except Exception:
        pass


def log(message: str, important=False, level="INFO"):
    from common.config_loader import DRY_RUN, LOG_FILE_PATH, LOG_LEVEL

    if level == "WARNING" and "[SmartSwitch]" in message and "No active trade found for" in message:
        try:
            from utils_core import load_state

            state = load_state()
            if state.get("stopping") or state.get("shutdown"):
                return
        except Exception:
            pass

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
        print(f"{Fore.RED}{full_msg}{Style.RESET_ALL}\n")
    else:
        if important or DRY_RUN or message_level >= LOG_LEVELS["WARNING"]:
            color = LOG_COLORS.get(level, Fore.WHITE)
            print(f"{color}{full_msg}{Style.RESET_ALL}\n")

            if message_level >= LOG_LEVELS["ERROR"]:
                with error_handling_guard() as allowed:
                    if allowed:
                        notify_error(message)


def get_recent_logs(n=50):
    from common.config_loader import LOG_FILE_PATH

    if not os.path.exists(LOG_FILE_PATH):
        log(f"Log file {LOG_FILE_PATH} not found.", level="WARNING")
        return "Log file not found."
    with open(LOG_FILE_PATH, encoding="utf-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


# def log_dry_entry(entry_data):
#     symbol = extract_symbol(entry_data.get("symbol", ""))
#     entry_price = entry_data.get("entry", 0)
#     direction = entry_data.get("direction", "N/A")
#     msg = f"DRY-RUN {symbol} {direction}@{entry_price}"
#     log(msg, important=False, level="INFO")


def now():
    return datetime.now()


def backup_config():
    backup_dir = "data/backups"
    source_file = "runtime_config.json"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_file = f"{backup_dir}/runtime_config_{timestamp}.json"
        shutil.copy(source_file, backup_file)
        send_telegram_message(
            f"📂 Config backup saved as {escape_markdown_v2(os.path.basename(backup_file))}",
            force=True,
        )
        log(f"Backed up config to {backup_file}", level="INFO")
    except Exception as e:
        log(f"Error backing up config: {e}", level="ERROR")
        send_telegram_message(f"❌ Error backing up config: {str(e)}", force=True)


def restore_config(backup_file=None):
    backup_dir = "data/backups"
    source_file = "runtime_config.json"
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if not backups:
            send_telegram_message("❌ No backups found", force=True)
            log("No config backups found.", level="WARNING")
            return
        if not backup_file:
            backup_file = backups[0]
        shutil.copy(f"{backup_dir}/{backup_file}", source_file)
        send_telegram_message(f"🔄 Restored config from {escape_markdown_v2(backup_file)}", force=True)
        log(f"Restored config from {backup_file}", level="INFO")
        if len(backups) > 5:
            for old in backups[5:]:
                os.remove(f"{backup_dir}/{old}")
            log("Cleaned up old backups, kept latest 5.", level="INFO")
    except Exception as e:
        log(f"Error restoring config: {e}", level="ERROR")
        send_telegram_message(f"❌ Error restoring config: {str(e)}", force=True)


def notify_ip_change(old_ip, new_ip, timestamp, forced_stop=False):
    try:
        message = f"⚠️ *IP Address Changed!*\n\n🕒 `{timestamp}`\n🌐 Old IP: `{old_ip}`\n🌐 New IP: `{new_ip}`\n"
        if forced_stop:
            message += "\n\n🚫 *Bot will stop after closing open orders.*\nYou can cancel this with `/cancel_stop`."
        send_telegram_message(message, force=True)
        log(f"IP changed from {old_ip} to {new_ip}", level="WARNING")
    except Exception as e:
        log(f"[notify_ip_change] Telegram error: {e}", level="ERROR")


def add_log_separator():
    from common.config_loader import LOG_FILE_PATH

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator_line = "=" * 80
    separator_message = f"\n\n{separator_line}\n NEW BOT RUN - {timestamp}\n{separator_line}\n\n"

    lock = FileLock(f"{LOG_FILE_PATH}.lock")
    try:
        with lock:
            if not os.path.exists(LOG_FILE_PATH):
                with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write("--- Telegram Log ---\n")
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(separator_message)

        print(f"\n{Fore.CYAN}{separator_line}")
        print(f"{Fore.CYAN} NEW BOT RUN - {timestamp}")
        print(f"{Fore.CYAN}{separator_line}\n{Style.RESET_ALL}")

    except Exception as e:
        error_msg = f"[ERROR] Failed to write separator to log file {LOG_FILE_PATH}: {e}"
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
