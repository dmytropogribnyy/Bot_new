# telegram_handler.py
"""
Telegram bot handler for BinanceBot
Processes Telegram updates and dispatches commands
"""

import os
import time

import requests

from common.config_loader import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from utils_logging import log

UPDATE_FILE = "data/last_update.txt"


def load_last_update_id():
    """
    Load the last processed update ID from file
    """
    if os.path.exists(UPDATE_FILE):
        with open(UPDATE_FILE, "r") as f:
            return int(f.read().strip())
    return None


def save_last_update_id(update_id: int):
    """
    Save the last processed update ID to file
    """
    with open(UPDATE_FILE, "w") as f:
        f.write(str(update_id))


def get_latest_update_id():
    """
    Fetch the latest update ID from Telegram API
    """
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("ok") and data.get("result"):
            return data["result"][-1]["update_id"]
    except Exception as e:
        log(f"⚠️ Failed to fetch latest update ID: {e}", level="ERROR")
    return None


# Initialize last update ID
last_update_id = load_last_update_id()
if last_update_id is None:
    latest_id = get_latest_update_id()
    last_update_id = latest_id + 1 if latest_id is not None else 0
    save_last_update_id(last_update_id)


def process_telegram_commands(state: dict, handler_fn):
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id}"
            response = requests.get(url, timeout=10)
            r = response.json()

            if not r.get("ok"):
                log(f"⚠️ Telegram API error: {r.get('description', 'Unknown error')}", level="ERROR")
                time.sleep(3)
                continue

            updates = r.get("result", [])

            for update in updates:
                update_id = update.get("update_id")
                if update_id is None or update_id < last_update_id:
                    continue

                message = update.get("message")
                if not isinstance(message, dict):
                    continue

                if "text" in message:
                    message["text"] = message["text"].encode("utf-8", errors="ignore").decode("utf-8")

                chat_id = message.get("chat", {}).get("id", 0)
                if str(chat_id) != TELEGRAM_CHAT_ID:
                    log(f"Unauthorized chat ID: {chat_id}", level="WARNING")
                    continue

                user_id = message.get("from", {}).get("id", 0)
                if user_id != state.get("allowed_user_id"):
                    log(f"Unauthorized user ID: {user_id}", level="WARNING")
                    continue

                log(f"🛰 Got command: {message.get('text')} from {user_id}", level="INFO")
                handler_fn(message, state)

                last_update_id = update_id + 1
                save_last_update_id(last_update_id)

        except Exception as e:
            log(f"⚠️ Telegram polling error: {e}", level="ERROR")
            time.sleep(3)
