#!/usr/bin/env python3
"""
Quick Telegram Message Sender
Send messages to your Telegram bot quickly
"""

import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def send_quick_message(message: str):
    """Send a quick message to Telegram"""
    try:
        # Initialize components
        config = TradingConfig()
        logger = UnifiedLogger(config)

        # Get Telegram credentials
        telegram_token, telegram_chat_id = config.get_telegram_credentials()

        if not telegram_token or not telegram_chat_id:
            print("❌ Telegram credentials not found!")
            return False

        # Create Telegram bot
        telegram_bot = TelegramBot(telegram_token, telegram_chat_id, logger)

        # Initialize
        success = await telegram_bot.initialize()
        if not success:
            print("❌ Failed to initialize Telegram bot")
            return False

        # Send message
        await telegram_bot.send_message(message)
        print("✅ Message sent successfully!")

        # Stop bot
        await telegram_bot.stop()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print('Usage: python send_telegram_message.py "Your message here"')
        print('Example: python send_telegram_message.py "Hello from BinanceBot!"')
        return

    message = sys.argv[1]
    print(f"📤 Sending message: {message}")

    success = await send_quick_message(message)

    if success:
        print("🎉 Message sent to Telegram!")
    else:
        print("❌ Failed to send message")


if __name__ == "__main__":
    asyncio.run(main())
