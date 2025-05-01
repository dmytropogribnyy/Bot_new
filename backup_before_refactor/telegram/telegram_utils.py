import requests

from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2, preserving emojis and formatting."""
    escape_chars = r"_*[]()~`>#+-=|{}.! "  # Включаем пробел
    return "".join("\\" + char if char in escape_chars else char for char in str(text))


def send_telegram_message(text: str, force=False, parse_mode="MarkdownV2"):
    from utils_logging import log  # Импорт внутри функции

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("[telegram_utils] Telegram not configured.", level="WARNING")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    if parse_mode == "MarkdownV2":
        escaped_text = escape_markdown_v2(text)
    else:
        escaped_text = text

    if len(escaped_text) > 4096:
        escaped_text = escaped_text[:4090] + "..."

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": escaped_text if isinstance(escaped_text, str) else str(escaped_text),
        "disable_notification": not force,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode
    else:
        payload["parse_mode"] = ""

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log(
                f"[telegram_utils] Message sent successfully: {escaped_text[:60]}...", level="DEBUG"
            )
        else:
            log(
                f"[telegram_utils] Telegram response {response.status_code}: {response.text}",
                level="ERROR",
            )
            # Fallback to plain text
            payload["parse_mode"] = ""
            payload["text"] = str(text)
            if len(payload["text"]) > 4096:
                payload["text"] = payload["text"][:4090] + "..."
            requests.post(url, json=payload, timeout=10)
            log(
                f"[telegram_utils] Sent as plain text (forced): {payload['text'][:60]}",
                level="INFO",
            )
    except Exception as e:
        log(f"[telegram_utils] Telegram send error: {e}", level="ERROR")
        # Fallback to plain text
        payload["parse_mode"] = ""
        payload["text"] = str(text)
        if len(payload["text"]) > 4096:
            payload["text"] = payload["text"][:4090] + "..."
        requests.post(url, json=payload, timeout=10)
        log(f"[telegram_utils] Sent as plain text (forced): {payload['text'][:60]}", level="INFO")


def send_telegram_file(file_path: str, caption: str = ""):
    """Send a file to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram_utils] Telegram not configured for file sending.")
        return
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                data=data,
                files=files,
                timeout=15,
            )
        if response.status_code == 200:
            print(f"[telegram_utils] File sent successfully: {file_path}")
        else:
            print(f"[telegram_utils] Failed to send file {file_path}: {response.text}")
    except Exception as e:
        print(f"[telegram_utils] Telegram file send error for {file_path}: {e}")


def send_telegram_image(image_path, caption=""):
    """Send image to Telegram via sendPhoto (inline preview)."""
    from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "MarkdownV2",
            }
            response = requests.post(url, data=data, files=files)
            if not response.ok:
                raise Exception(f"Telegram image upload failed: {response.text}")
    except Exception as e:
        print(f"[Telegram] Failed to send image: {e}")
