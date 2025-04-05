import json
import os
import shutil
import time
from datetime import datetime
from threading import Lock  # Для потокобезопасности

from colorama import Fore, Style, init  # For colored console output
from filelock import FileLock  # For thread-safe file access

from config import DRY_RUN, LOG_FILE_PATH, LOG_LEVEL, TIMEZONE, exchange
from telegram.telegram_utils import escape_markdown_v2, send_telegram_message

# Initialize colorama for cross-platform support
init(autoreset=True)

# Define STATE_FILE
STATE_FILE = "data/bot_state.json"

# Default state to use in case of errors or missing file
DEFAULT_STATE = {
    "pause": False,
    "stopping": False,
    "shutdown": False,
    "allowed_user_id": 383821734,
}

# Log levels
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

# Log rotation settings
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB in bytes
BACKUP_COUNT = 5  # Keep up to 5 backup files

# Color mapping for console output
LOG_COLORS = {
    "DEBUG": Fore.CYAN,
    "INFO": Fore.WHITE,  # Changed from Fore.GREEN to Fore.WHITE
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
}

# Глобальный кэш с потокобезопасностью
CACHE_TTL = 30  # Cache TTL in seconds
api_cache = {
    "balance": {"value": None, "timestamp": 0},
    "positions": {"value": [], "timestamp": 0},
}
cache_lock = Lock()  # Блокировка для доступа к api_cache


def notify_error(msg):
    """Notify an error via Telegram."""
    send_telegram_message(f"❌ {escape_markdown_v2(str(msg))}", force=True)


def log(message: str, important=False, level="INFO"):
    """
    Log a message to a file with rotation and optionally to the console with colors.
    Args:
        message (str): The message to log.
        important (bool): If True, always print to console regardless of DRY_RUN.
        level (str): Log level ("DEBUG", "INFO", "WARNING", "ERROR").
    """
    message_level = LOG_LEVELS.get(level, LOG_LEVELS["INFO"])
    min_level = LOG_LEVELS.get(LOG_LEVEL, LOG_LEVELS["INFO"])
    if message_level < min_level:
        return

    timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] [{level}] {message}"

    # Ensure the log directory exists, but skip if the directory path is empty
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir:  # Only call makedirs if there's a directory component
        os.makedirs(log_dir, exist_ok=True)

    lock = FileLock(f"{LOG_FILE_PATH}.lock")
    try:
        with lock:
            if os.path.exists(LOG_FILE_PATH):
                file_size = os.path.getsize(LOG_FILE_PATH)
                if file_size > MAX_LOG_SIZE:
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
        print()  # Добавляем пустую строку при ошибке

    if important or DRY_RUN or message_level >= LOG_LEVELS["WARNING"]:
        color = LOG_COLORS.get(level, Fore.WHITE)
        print(f"{color}{full_msg}{Style.RESET_ALL}")
        print()  # Добавляем пустую строку после каждого сообщения


def get_recent_logs(n=50):
    """Get the last n lines from the log file."""
    if not os.path.exists(LOG_FILE_PATH):
        log(f"Log file {LOG_FILE_PATH} not found.", level="WARNING")
        return "Log file not found."
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


def get_last_signal_time():
    """Get the timestamp of the last signal."""
    path = "data/last_signal.txt"
    if not os.path.exists(path):
        log(f"Last signal file {path} not found.", level="INFO")
        return None
    try:
        with open(path, "r") as f:
            ts = f.read().strip()
            return datetime.fromisoformat(ts)
    except Exception as e:
        log(f"Error reading last signal time from {path}: {e}", level="ERROR")
        return None


def update_last_signal_time():
    """Update the timestamp of the last signal."""
    path = "data/last_signal.txt"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(datetime.now().isoformat())
        log(f"Updated last signal time in {path}.", level="INFO")
    except Exception as e:
        log(f"Error updating last signal time in {path}: {e}", level="ERROR")


def get_open_symbols():
    """Get a list of symbols with open positions."""
    try:
        open_syms = []
        positions = get_cached_positions()
        for p in positions:
            if float(p.get("contracts", 0)) > 0:
                open_syms.append(p["symbol"])
        log(f"Fetched open symbols: {open_syms}", level="INFO")
        return open_syms
    except Exception as e:
        log(f"Error fetching open symbols: {e}", level="ERROR")
        return []


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


def now():
    """Get the current time in the configured timezone."""
    return datetime.now(TIMEZONE)


def log_dry_entry(entry_data):
    """Log a dry run entry."""
    log(f"Dry entry log: {entry_data}", important=False, level="INFO")


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


def get_cached_balance():
    """Получить баланс из кэша или обновить через API."""
    with cache_lock:
        now = time.time()
        if (
            now - api_cache["balance"]["timestamp"] > CACHE_TTL
            or api_cache["balance"]["value"] is None
        ):
            try:
                api_cache["balance"]["value"] = exchange.fetch_balance()["total"]["USDC"]
                api_cache["balance"]["timestamp"] = now
                log(
                    f"Updated balance cache: {api_cache['balance']['value']} USDC",
                    level="DEBUG",
                )
            except Exception as e:
                log(f"Error fetching balance: {e}", level="ERROR")
                return (
                    api_cache["balance"]["value"]
                    if api_cache["balance"]["value"] is not None
                    else 0.0
                )
        return api_cache["balance"]["value"]


def get_cached_positions():
    """Получить позиции из кэша или обновить через API."""
    with cache_lock:
        now = time.time()
        if (
            now - api_cache["positions"]["timestamp"] > CACHE_TTL
            or not api_cache["positions"]["value"]
        ):
            try:
                api_cache["positions"]["value"] = exchange.fetch_positions()
                api_cache["positions"]["timestamp"] = now
                log(
                    f"Updated positions cache: {len(api_cache['positions']['value'])} positions",
                    level="DEBUG",
                )
            except Exception as e:
                log(f"Error fetching positions: {e}", level="ERROR")
                return api_cache["positions"]["value"] if api_cache["positions"]["value"] else []
        return api_cache["positions"]["value"]


def initialize_cache():
    """Инициализация кэша при старте бота."""
    get_cached_balance()
    get_cached_positions()
    log("API cache initialized", level="INFO")


def load_state():
    """
    Load the bot's state from a JSON file.
    Returns the state as a dict, or a default state if the file doesn't exist or is invalid.
    The state is guaranteed to contain all keys from DEFAULT_STATE.
    """
    try:
        if not os.path.exists(STATE_FILE):
            return DEFAULT_STATE.copy()
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            for key, value in DEFAULT_STATE.items():
                if key not in state:
                    state[key] = value
            return state
    except json.JSONDecodeError as e:
        log(
            f"Error decoding state file {STATE_FILE}: {e}. Using default state.",
            important=True,
            level="ERROR",
        )
        send_telegram_message(
            f"❌ Error decoding state file {STATE_FILE}: {str(e)}. Reset to default state.",
            force=True,
        )
        return DEFAULT_STATE.copy()
    except Exception as e:
        log(
            f"Unexpected error loading state file {STATE_FILE}: {e}. Using default state.",
            important=True,
            level="ERROR",
        )
        send_telegram_message(
            f"❌ Unexpected error loading state file {STATE_FILE}: {str(e)}. Reset to default state.",
            force=True,
        )
        return DEFAULT_STATE.copy()


def save_state(state, retries=3, delay=1):
    """
    Save the bot's state to a JSON file with retry logic.
    Args:
        state (dict): The state to save.
        retries (int): Number of retry attempts if saving fails.
        delay (float): Delay in seconds between retries.
    """
    attempt = 0
    while attempt < retries:
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
            return
        except Exception as e:
            attempt += 1
            log(
                f"Attempt {attempt}/{retries} - Error saving state to {STATE_FILE}: {e}",
                important=True,
                level="ERROR",
            )
            if attempt == retries:
                send_telegram_message(
                    f"❌ Failed to save state to {STATE_FILE} after {retries} attempts: {str(e)}",
                    force=True,
                )
            else:
                time.sleep(delay)


if __name__ == "__main__":
    # Тестовый запуск для проверки кэширования
    initialize_cache()
    print(f"Balance: {get_cached_balance()}")
    print(f"Positions: {len(get_cached_positions())}")
