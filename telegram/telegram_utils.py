import requests

from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2, preserving emojis and formatting."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join("\\" + char if char in escape_chars else char for char in str(text))


def send_telegram_message(text: str, force=False):
    """Send a message to Telegram with MarkdownV2 support."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram_utils] Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Экранируем текст
    escaped_text = escape_markdown_v2(text)
    # Логируем экранированный текст для отладки
    print(f"[telegram_utils] Sending message: {escaped_text}")
    # Обрезаем, если нужно
    if len(escaped_text) > 4096:
        escaped_text = escaped_text[:4090] + "..."
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": escaped_text,
        "parse_mode": "MarkdownV2",
        "disable_notification": not force,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[telegram_utils] Message sent successfully: {text[:60]}...")
        else:
            print(f"[telegram_utils] Telegram response {response.status_code}: {response.text}")
            # Fallback to plain text
            payload["parse_mode"] = ""
            payload["text"] = text
            if len(payload["text"]) > 4096:
                payload["text"] = payload["text"][:4090] + "..."
            requests.post(url, json=payload, timeout=10)
            print(f"[telegram_utils] Sent as plain text (forced): {text[:60]}")
    except Exception as e:
        print(f"[telegram_utils] Telegram send error: {e}")
        # Fallback to plain text
        payload["parse_mode"] = ""
        payload["text"] = text
        if len(payload["text"]) > 4096:
            payload["text"] = payload["text"][:4090] + "..."
        requests.post(url, json=payload, timeout=10)
        print(f"[telegram_utils] Sent as plain text (forced): {text[:60]}")


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
