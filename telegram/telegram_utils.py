# telegram_utils.py
"""
Utilities for sending Telegram messages, files, and images
"""

import os

import pandas as pd
import requests

_in_telegram_send = False


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2, preserving emojis and formatting
    """
    escape_chars = r"_*[]()~`>#+-=|{}.! "  # Включаем пробел
    return "".join("\\" + char if char in escape_chars else char for char in str(text))


def send_telegram_message(text: str, force=False, parse_mode="MarkdownV2"):
    """
    Send a message to Telegram with automatic fallback to plain text for errors
    """
    from common.config_loader import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
    from utils_logging import log

    # Anti-recursion protection
    global _in_telegram_send
    if _in_telegram_send:
        # We're already inside this function, don't recurse
        print(f"[PREVENTED RECURSION] Telegram message: {text[:50]}...")
        return False

    _in_telegram_send = True

    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            log(f"[telegram_utils] Telegram not configured: TOKEN={'Set' if TELEGRAM_TOKEN else 'Not set'}, CHAT_ID={'Set' if TELEGRAM_CHAT_ID else 'Not set'}", level="WARNING")
            return False

        # Automatically switch to plain text for error and warning messages
        if any(marker in text for marker in ["⚠️", "❌", "Error", "error", "[ERROR]", "cannot import", "failed", "Failed"]):
            parse_mode = ""  # Use plain text for error messages
            log("[telegram_utils] Switched to plain text mode for error message", level="DEBUG")

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

        try:
            import time

            time.sleep(0.1)  # Add rate-limiting delay
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                log(f"[telegram_utils] Message sent successfully: {escaped_text[:60]}...", level="DEBUG")
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
                time.sleep(0.1)  # Rate-limiting delay for retry
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
            try:
                time.sleep(0.1)  # Rate-limiting delay for retry
                requests.post(url, json=payload, timeout=10)
                log(
                    f"[telegram_utils] Sent as plain text (forced): {payload['text'][:60]}",
                    level="INFO",
                )
            except Exception as e2:
                log(f"[telegram_utils] Final attempt failed: {e2}", level="ERROR")

        return True
    finally:
        # Always reset the recursion flag, even if there's an exception
        _in_telegram_send = False


def send_telegram_file(file_path: str, caption: str = ""):
    """
    Send a file to Telegram
    """
    from common.config_loader import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
    from utils_logging import log

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log(f"[telegram_utils] Telegram not configured for file sending: TOKEN={'Set' if TELEGRAM_TOKEN else 'Not set'}, CHAT_ID={'Set' if TELEGRAM_CHAT_ID else 'Not set'}", level="WARNING")
        return

    # Telegram limits caption length to 1024 characters for documents
    if len(caption) > 1024:
        caption = caption[:1018] + "..."
        log("[telegram_utils] Caption truncated to 1024 characters", level="DEBUG")

    try:
        import time

        time.sleep(0.1)  # Rate-limiting delay
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
            log(f"[telegram_utils] File sent successfully: {file_path}", level="INFO")
        else:
            log(f"[telegram_utils] Failed to send file {file_path}: {response.text}", level="ERROR")
    except Exception as e:
        log(f"[telegram_utils] Telegram file send error for {file_path}: {e}", level="ERROR")


def send_telegram_image(image_path: str, caption: str = ""):
    """
    Send image to Telegram via sendPhoto (inline preview)
    """
    from common.config_loader import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
    from utils_logging import log

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log(
            f"[telegram_utils] Telegram not configured for image sending: TOKEN={'Set' if TELEGRAM_TOKEN else 'Not set'}, CHAT_ID={'Set' if TELEGRAM_CHAT_ID else 'Not set'}", level="WARNING"
        )
        return

    # Telegram limits caption length to 1024 characters for photos
    if len(caption) > 1024:
        caption = caption[:1018] + "..."
        log("[telegram_utils] Caption truncated to 1024 characters", level="DEBUG")

    try:
        import time

        time.sleep(0.1)  # Rate-limiting delay
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "MarkdownV2",
            }
            response = requests.post(url, data=data, files=files, timeout=15)
            if response.ok:
                log(f"[telegram_utils] Image sent successfully: {image_path}", level="INFO")
            else:
                raise Exception(f"Telegram image upload failed: {response.text}")
    except Exception as e:
        log(f"[telegram_utils] Failed to send image: {e}", level="ERROR")


def send_daily_summary():
    from common.config_loader import EXPORT_PATH
    from utils_logging import log

    try:
        if not os.path.exists(EXPORT_PATH):
            log(f"[telegram_utils] Export file not found: {EXPORT_PATH}", level="WARNING")
            return

        df = pd.read_csv(EXPORT_PATH, parse_dates=["Date"])
        today = pd.Timestamp.now().normalize()

        today_trades = df[df["Date"] >= today]

        if today_trades.empty:
            send_telegram_message("📋 No trades closed today.", force=True)
            return

        total_trades = len(today_trades)
        wins = len(today_trades[today_trades["Result"].isin(["TP1", "TP2"])])
        losses = len(today_trades[today_trades["Result"] == "SL"])
        avg_pnl = today_trades["PnL (%)"].mean()

        message = f"📈 *Daily Trading Summary*\n" f"Total Trades: {total_trades}\n" f"Wins: {wins}\n" f"Losses: {losses}\n" f"Avg PnL: {avg_pnl:.2f}%"

        send_telegram_message(escape_markdown_v2(message))
    except Exception as e:
        send_telegram_message(escape_markdown_v2(f"⚠️ Failed to send daily summary:\n{e}"))
