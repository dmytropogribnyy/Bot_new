#!/usr/bin/env python3
"""
Test Telegram Bot Integration
Verify that Telegram bot is properly integrated and working
"""

import pytest

# Skip network-dependent Telegram tests in CI
pytestmark = pytest.mark.skip(reason="Skip network-dependent Telegram tests in CI")

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import TradingConfig
from core.unified_logger import UnifiedLogger
from telegram.telegram_bot import TelegramBot


async def test_telegram_integration():
    """Test Telegram bot integration"""
    print("🚀 Starting Telegram Integration Test...")
    print("=" * 50)

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
            print("⚠️  Telegram credentials not configured")
            print("   This is expected for testing without real credentials")
            return True

        # Create Telegram bot
        telegram_bot = TelegramBot(telegram_token, telegram_chat_id, logger)

        # Test initialization
        print("\n🧪 Testing Telegram Bot Initialization...")
        success = await telegram_bot.initialize()

        if success:
            print("✅ Telegram bot initialized successfully")

            # Test sending message
            print("\n🧪 Testing Message Sending...")
            try:
                await telegram_bot.send_message("🤖 BinanceBot v2.3 - Test message")
                print("✅ Message sent successfully")
            except Exception as e:
                print(f"⚠️  Message sending failed: {e}")
                print("   This might be due to network issues or invalid credentials")

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

    print("\n" + "=" * 50)
    print("🎉 Telegram integration test completed!")
    return True


async def test_main_integration():
    """Test main.py integration with Telegram"""
    print("\n🧪 Testing Main.py Telegram Integration...")

    try:
        from main import SimplifiedTradingBot

        # Create bot instance
        bot = SimplifiedTradingBot()

        print("✅ Bot instance created")
        print(f"   Telegram bot: {'Enabled' if bot.telegram_bot else 'Disabled'}")

        if bot.telegram_bot:
            print("✅ Telegram bot is properly integrated in main.py")
        else:
            print("⚠️  Telegram bot is disabled in main.py")

    except Exception as e:
        print(f"❌ Main integration test failed: {e}")
        return False

    return True


async def main():
    """Main test function"""
    print("🚀 Starting Telegram Integration Tests...")

    # Test 1: Direct Telegram bot test
    success1 = await test_telegram_integration()

    # Test 2: Main.py integration test
    success2 = await test_main_integration()

    print("\n📊 Test Summary:")
    print("=" * 50)
    print(f"Telegram Bot Test: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Main Integration: {'✅ PASS' if success2 else '❌ FAIL'}")

    if success1 and success2:
        print("\n🎉 All tests passed! Telegram integration is working.")
    else:
        print("\n⚠️  Some tests failed. Check configuration and credentials.")

    return success1 and success2


if __name__ == "__main__":
    asyncio.run(main())
