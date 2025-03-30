import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, LOG_FILE_PATH, VERBOSE


def send_telegram_message(message: str, force: bool = False):
    if not VERBOSE and not force:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})
    except:
        pass


def send_telegram_file(filepath: str, force: bool = False):
    if not VERBOSE and not force:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(filepath, 'rb') as f:
            requests.post(url, files={'document': f}, data={'chat_id': TELEGRAM_CHAT_ID})
    except:
        send_telegram_message("❌ Failed to send file.", force=True)


def process_telegram_commands(state: dict):
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates").json()
        for msg in r.get("result", [])[-5:]:
            text = msg.get("message", {}).get("text", "")
            uid = msg.get("message", {}).get("from", {}).get("id", 0)
            if uid != state.get('allowed_user_id'):
                continue

            cmd = text.upper()
            if cmd == "/HELP":
                send_telegram_message("/help /export /summary /pause /resume /open /closeall /log /risk", force=True)
            elif cmd == "/PAUSE":
                state['pause'] = True
                send_telegram_message("⏸️ Trading paused", force=True)
            elif cmd == "/RESUME":
                state['pause'] = False
                send_telegram_message("▶️ Trading resumed", force=True)
            elif cmd == "/LOG":
                try:
                    with open(LOG_FILE_PATH, 'rb') as f:
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                                      data={'chat_id': TELEGRAM_CHAT_ID},
                                      files={'document': f})
                except:
                    send_telegram_message("❌ Log unavailable.", force=True)
    except:
        pass
