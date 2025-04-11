import os
import time

import requests

from config import TELEGRAM_TOKEN, VERBOSE

UPDATE_FILE = "data/last_update.txt"


def load_last_update_id():
    if os.path.exists(UPDATE_FILE):
        with open(UPDATE_FILE, "r") as f:
            return int(f.read().strip())
    return None


def save_last_update_id(update_id: int):
    with open(UPDATE_FILE, "w") as f:
        f.write(str(update_id))


def get_latest_update_id():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("ok") and data.get("result"):
            return data["result"][-1]["update_id"]
    except Exception as e:
        if VERBOSE:
            print(f"⚠️ Failed to fetch latest update ID: {e}")
    return None


last_update_id = load_last_update_id()
if last_update_id is None:
    latest_id = get_latest_update_id()
    last_update_id = latest_id + 1 if latest_id is not None else 0
    save_last_update_id(last_update_id)


def process_telegram_commands(state: dict, handler_fn):
    global last_update_id
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id}",
                timeout=10,
            ).json()

            updates = r.get("result", [])

            for update in updates:
                update_id = update.get("update_id")
                if update_id is None or update_id < last_update_id:
                    continue

                message = update.get("message")
                if not isinstance(message, dict):
                    continue

                if "text" in message:
                    message["text"] = (
                        message["text"].encode("utf-8", errors="ignore").decode("utf-8")
                    )

                user_id = message.get("from", {}).get("id", 0)
                if user_id != state.get("allowed_user_id"):
                    continue

                print(f"🛰 Got command: {message.get('text')} from {user_id}")
                handler_fn(message, state)

                last_update_id = update_id + 1
                save_last_update_id(last_update_id)

        except Exception as e:
            if VERBOSE:
                print(f"⚠️ Telegram polling error: {e}")

        time.sleep(3)
