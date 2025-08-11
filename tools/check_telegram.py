#!/usr/bin/env python3
"""
Quick Telegram connectivity check.
Requires env:
  TELEGRAM_ENABLED=true
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
"""

import sys

from core.config import env_bool

try:
    from telegram.telegram_utils import send_telegram_message
except Exception as e:
    print(f"Import error: {e}")
    sys.exit(1)

if not env_bool("TELEGRAM_ENABLED", False):
    print("TELEGRAM_ENABLED is not true; set it and retry.")
    sys.exit(2)

msg = "📡 Telegram ping: test message from tools/check_telegram.py"
try:
    send_telegram_message(msg, force=True)
    print("OK: message sent.")
except Exception as e:
    print(f"ERROR sending message: {e}")
    sys.exit(3)
