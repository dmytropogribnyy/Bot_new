#!/usr/bin/env python3
"""
Test Real Telegram Message
Send a real message to Telegram bot using credentials from .env
"""

import pytest

# Skip network-dependent Telegram tests in CI
pytestmark = pytest.mark.skip(reason="Skip network-dependent Telegram tests in CI")

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def send_real_telegram_message():
    """Send a real message to Telegram bot"""
    print("🚀 Starting Real Telegram Message Test...")
    print("=" * 60)

    try:
        # Initialize components
        config = TradingConfig()
        logger = UnifiedLogger(config)

        # Get Telegram credentials
        telegram_token, telegram_chat_id = config.get_telegram_credentials()

        print("📱 Telegram Configuration:")
        print(f"   Token: {'*' * 10 if telegram_token else 'NOT SET'}")
        print(f"   Chat ID: {telegram_chat_id or 'NOT SET'}")

        if not telegram_token or not telegram_chat_id:
            print("\n⚠️  Telegram credentials not found!")
            print("   Please add to .env file:")
            print("   TELEGRAM_TOKEN=your_bot_token")
            print("   TELEGRAM_CHAT_ID=your_chat_id")
            print("\n   Or set environment variables:")
            print("   $env:TELEGRAM_TOKEN='your_bot_token'")
            print("   $env:TELEGRAM_CHAT_ID='your_chat_id'")
            return False

        # Create Telegram bot
        telegram_bot = TelegramBot(telegram_token, telegram_chat_id, logger)

        # Test initialization
        print("\n🧪 Initializing Telegram Bot...")
        success = await telegram_bot.initialize()

        if success:
            print("✅ Telegram bot initialized successfully")

            # Send test message
            test_message = """
🤖 BinanceBot v2.3 - Test Message

📊 Status: Stage 2 Revision Completed
✅ All components working
✅ Strategy integration ready
✅ Telegram bot enabled
✅ Runtime logging active

🔄 Next: Stage 3 - DRY RUN Testing
📅 Date: 6 August 2025
            """.strip()

            print("\n📤 Sending test message...")
            print(f"Message length: {len(test_message)} characters")

            try:
                await telegram_bot.send_message(test_message)
                print("✅ Message sent successfully!")
                print("📱 Check your Telegram for the message")

                # Wait a moment and send a second message
                await asyncio.sleep(2)

                status_message = """
📈 Bot Status Update:
• Configuration: ✅ Loaded
• Exchange Client: ✅ Ready
• Order Manager: ✅ Active
• Strategy Manager: ✅ Integrated
• Symbol Manager: ✅ Working
• Telegram Bot: ✅ Connected

🎯 Ready for Stage 3 testing!
                """.strip()

                await telegram_bot.send_message(status_message)
                print("✅ Status message sent successfully!")

            except Exception as e:
                print(f"❌ Failed to send message: {e}")
                print("   This might be due to:")
                print("   - Invalid bot token")
                print("   - Invalid chat ID")
                print("   - Network issues")
                print("   - Bot not started")
                return False

            # Stop bot
            await telegram_bot.stop()
            print("✅ Telegram bot stopped")

        else:
            print("❌ Telegram bot initialization failed")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return False

    print("\n" + "=" * 60)
    print("🎉 Real Telegram message test completed!")
    return True


async def setup_telegram_credentials():
    """Helper to set up Telegram credentials"""
    print("\n🔧 Setting up Telegram credentials...")

    # Check if credentials are already set
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        print("✅ Telegram credentials found in environment")
        return True

    print("⚠️  Telegram credentials not found in environment")
    print("\n📝 To add credentials, you can:")
    print("1. Add to .env file:")
    print("   TELEGRAM_TOKEN=your_bot_token")
    print("   TELEGRAM_CHAT_ID=your_chat_id")
    print("\n2. Or set environment variables:")
    print("   $env:TELEGRAM_TOKEN='your_bot_token'")
    print("   $env:TELEGRAM_CHAT_ID='your_chat_id'")

    return False


async def main():
    """Main test function"""
    print("🚀 Starting Real Telegram Message Test...")

    # Check credentials
    credentials_ok = await setup_telegram_credentials()

    if not credentials_ok:
        print("\n❌ Cannot proceed without Telegram credentials")
        return False

    # Send real message
    success = await send_real_telegram_message()

    if success:
        print("\n🎉 SUCCESS! Message sent to Telegram!")
        print("📱 Check your Telegram chat for the messages")
    else:
        print("\n❌ Failed to send message")
        print("   Please check your credentials and try again")

    return success


if __name__ == "__main__":
    asyncio.run(main())
